from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel
from sqlmodel import Field as SqlField

from .. import __version__


def _uuid() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class VersionOut(BaseModel):
    version: str

    @classmethod
    def from_metadata(cls):
        return cls(version=__version__)


# --- Lakebase tables (created by lakebase/setup.sql) ---


class IntakeRequest(SQLModel, table=True):
    __tablename__ = "intake_requests"
    __table_args__ = {"schema": "app"}
    request_id: str = SqlField(default_factory=_uuid, primary_key=True)
    title: str
    description: str
    business_unit: str | None = None
    requester_email: str
    sponsor: str | None = None
    problem_statement: str | None = None
    expected_benefit: str | None = None
    est_value_usd: float | None = None
    data_sources: str | None = None
    urgency: str | None = None
    status: str = "submitted"
    category: str | None = None
    category_confidence: float | None = None
    duplicate_of: str | None = None
    dup_score: float | None = None
    dup_check_failed: bool = False
    submit_anyway_reason: str | None = None
    extra_fields: dict[str, Any] = SqlField(default_factory=dict, sa_column=Column(JSONB, nullable=False))
    submitted_at: datetime = SqlField(default_factory=_now)
    updated_at: datetime = SqlField(default_factory=_now)


class ReviewDecision(SQLModel, table=True):
    __tablename__ = "review_decisions"
    __table_args__ = {"schema": "app"}
    decision_id: str = SqlField(default_factory=_uuid, primary_key=True)
    request_id: str
    reviewer_email: str
    action: str
    merged_into: str | None = None
    reason: str | None = None
    decided_at: datetime = SqlField(default_factory=_now)


# --- API models ---

Band = Literal["likely_duplicate", "related", "none"]


class FormFieldOut(BaseModel):
    field_name: str
    label: str
    type: str
    required: bool
    options: list[str] | None = None
    display_order: int


class FormConfigOut(BaseModel):
    organization_label: str
    fields: list[FormFieldOut]
    categories: list[str]
    thresholds: dict[str, float]
    duplicate_check: dict[str, int]


class DuplicateCheckIn(BaseModel):
    title: str = ""
    description: str = ""
    draft_id: str | None = None


class DuplicateMatch(BaseModel):
    key: str
    kind: str
    title: str
    score: float
    band: Band
    status: str | None
    owner: str | None
    business_unit: str | None


class DuplicateCheckOut(BaseModel):
    matches: list[DuplicateMatch]
    cached: bool
    elapsed_ms: int


class RequestIn(BaseModel):
    fields: dict[str, Any]
    dup_score: float | None = None
    dup_check_failed: bool = False
    submit_anyway_reason: str | None = None
    join_existing: str | None = Field(default=None, description="Key of the request or project to join")
    submission_id: str | None = Field(default=None, description="Client id for the form; a resend returns the saved row")


class RequestOut(BaseModel):
    request_id: str
    title: str
    business_unit: str | None
    status: str
    category: str | None
    category_confidence: float | None
    duplicate_of: str | None
    dup_score: float | None
    dup_check_failed: bool
    submit_anyway_reason: str | None
    est_value_usd: float | None
    requester_email: str
    submitted_at: datetime | None
    classify_ms: int | None = None


class ReviewItemOut(RequestOut):
    description: str
    top_match: DuplicateMatch | None = None


class ReviewIn(BaseModel):
    action: Literal["approve", "merge", "reject"]
    merged_into: str | None = None
    reason: str | None = None


class ReviewOut(BaseModel):
    decision_id: str
    request_id: str
    action: str
    status: str


class PortfolioOut(BaseModel):
    request_count: int
    total_est_value: float
    open_backlog_value: float
    duplicate_rate: float
    genie_url: str | None


class GenieConfigOut(BaseModel):
    configured: bool
    questions: list[str]
    runs_as: Literal["user"] = "user"


class GenieAskIn(BaseModel):
    question: str
    conversation_id: str | None = None


class GenieAskOut(BaseModel):
    conversation_id: str
    answer: str
    sql: str | None = None
    columns: list[str] = []
    rows: list[list[str]] = []


class MatchDetailOut(BaseModel):
    """Full detail for one duplicate match, shown before the requester confirms Join existing."""
    kind: str
    key: str
    title: str
    description: str | None
    status: str | None
    owner: str | None
    business_unit: str | None
    est_value_usd: float | None
    category: str | None
    updated_at: datetime | None
