"""Lakebase Autoscaling integration: engine with OAuth token refresh, session dependency.

Deployed apps get PGHOST, PGDATABASE, PGUSER, and LAKEBASE_ENDPOINT from the `postgres` app
resource. Locally, LAKEBASE_PROJECT / LAKEBASE_BRANCH resolve the endpoint and host via the SDK.
Tables are created by lakebase/setup.sql, not by the app.
"""

from __future__ import annotations

import os
import time
from collections.abc import Generator
from contextlib import asynccontextmanager
from typing import Annotated, Any, AsyncGenerator, TypeAlias

from databricks.sdk import WorkspaceClient
from fastapi import FastAPI, Request
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Engine, create_engine, event
from sqlmodel import Session, text

from ._base import LifespanDependency
from ._config import logger

TOKEN_TTL_SECONDS = 50 * 60  # credentials last one hour; refresh early


class DatabaseConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="")

    endpoint: str | None = Field(default=None, validation_alias="LAKEBASE_ENDPOINT")
    project: str = Field(default="oneintake", validation_alias="LAKEBASE_PROJECT")
    branch: str = Field(default="production", validation_alias="LAKEBASE_BRANCH")
    host: str | None = Field(default=None, validation_alias="PGHOST")
    port: int = Field(default=5432, validation_alias="PGPORT")
    database: str = Field(default="databricks_postgres", validation_alias="PGDATABASE")
    user: str | None = Field(default=None, validation_alias="PGUSER")

    def endpoint_name(self) -> str:
        return self.endpoint or f"projects/{self.project}/branches/{self.branch}/endpoints/primary"


class _TokenCache:
    def __init__(self, ws: WorkspaceClient, endpoint: str):
        self.ws, self.endpoint = ws, endpoint
        self.token, self.expires = "", 0.0

    def get(self) -> str:
        if time.monotonic() >= self.expires:
            self.token = self.ws.postgres.generate_database_credential(endpoint=self.endpoint).token
            self.expires = time.monotonic() + TOKEN_TTL_SECONDS
        return self.token


def create_db_engine(cfg: DatabaseConfig, ws: WorkspaceClient) -> Engine:
    endpoint = cfg.endpoint_name()
    host = cfg.host or ws.postgres.get_endpoint(name=endpoint).status.hosts.host
    user = cfg.user or ws.config.client_id or ws.current_user.me().user_name
    logger.info(f"Using Lakebase endpoint {endpoint} database {cfg.database}")
    kwargs: dict[str, Any] = {"pool_size": 5, "max_overflow": 5, "pool_pre_ping": True,
                              "pool_recycle": 45 * 60, "connect_args": {"sslmode": "require"}}
    engine = create_engine(f"postgresql+psycopg://{user}:@{host}:{cfg.port}/{cfg.database}", **kwargs)
    tokens = _TokenCache(ws, endpoint)

    @event.listens_for(engine, "do_connect")
    def _password(dialect, conn_rec, cargs, cparams):
        cparams["password"] = tokens.get()

    return engine


class _LakebaseDependency(LifespanDependency):
    @asynccontextmanager
    async def lifespan(self, app: FastAPI) -> AsyncGenerator[None, None]:
        if os.environ.get("ONEINTAKE_SKIP_DB") == "1":
            yield
            return
        engine = create_db_engine(DatabaseConfig(), app.state.workspace_client)
        with Session(engine) as s:
            s.connection().execute(text("SELECT 1"))
        logger.info("Lakebase connection validated")
        app.state.engine = engine
        yield
        engine.dispose()

    @staticmethod
    def __call__(request: Request) -> Generator[Session, None, None]:
        with Session(bind=request.app.state.engine) as session:
            yield session


LakebaseDependency: TypeAlias = Annotated[Session, _LakebaseDependency.depends()]
