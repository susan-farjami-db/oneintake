import logging
import os
import time
from datetime import datetime, timezone

from databricks.sdk.service.iam import User as UserOut
from fastapi import HTTPException
from sqlmodel import col, select, text

from . import services as svc
from .core import Dependencies, create_router
from .models import (DuplicateCheckIn, DuplicateCheckOut, FormConfigOut, FormFieldOut,
                     PortfolioOut,
                     IntakeRequest, RequestIn, RequestOut, ReviewDecision, ReviewIn, ReviewItemOut, ReviewOut)

router = create_router()
log = logging.getLogger(__name__)
COLUMNS = {f["field_name"] for f in svc.form_fields()} & set(IntakeRequest.model_fields)


@router.get("/current-user", response_model=UserOut, operation_id="currentUser")
def me(user_ws: Dependencies.UserClient):
    return user_ws.current_user.me()


@router.get("/form-config", response_model=FormConfigOut, operation_id="formConfig")
def form_config(session: Dependencies.Session, ws: Dependencies.Client):
    svc.warm_up(ws)
    rows = session.execute(text("SELECT field_name, label, type, required, options, display_order "
                                "FROM app.form_config ORDER BY display_order")).mappings()
    labels = session.execute(text("SELECT label FROM app.category_labels WHERE active ORDER BY label")).scalars()
    cfg = svc.app_config()
    return FormConfigOut(organization_label=cfg["organization_label"], fields=[FormFieldOut(**r) for r in rows],
                         categories=list(labels), thresholds=cfg["thresholds"],
                         duplicate_check=cfg["duplicate_check"])


@router.post("/requests/check-duplicates", response_model=DuplicateCheckOut, operation_id="checkDuplicates")
def check_duplicates(body: DuplicateCheckIn, ws: Dependencies.Client, user_ws: Dependencies.UserClient,
                     session: Dependencies.Session):
    start = time.perf_counter()
    email, _ = svc.identity(user_ws)
    svc.rate_limiter.check(email)
    query = svc.normalize(body.title, body.description)
    if not query:
        return DuplicateCheckOut(matches=[], cached=False, elapsed_ms=0)
    vec, cached = svc.embeddings.get_or_embed(ws, query, query=True)
    matches = svc.find_duplicates(session, vec, body.draft_id)
    return DuplicateCheckOut(matches=matches, cached=cached, elapsed_ms=int((time.perf_counter() - start) * 1000))


def _to_out(r: IntakeRequest, classify_ms: int | None = None) -> RequestOut:
    return RequestOut(**r.model_dump(include=set(RequestOut.model_fields)), classify_ms=classify_ms)


@router.post("/requests", response_model=RequestOut, operation_id="createRequest")
def create_request(body: RequestIn, ws: Dependencies.Client, user_ws: Dependencies.UserClient,
                   session: Dependencies.Session):
    email, _ = svc.identity(user_ws)
    fields = dict(body.fields)
    missing = [f["field_name"] for f in svc.form_fields()
               if f["required"] and f["field_name"] != "requester_email" and fields.get(f["field_name"]) in (None, "", [])]
    if missing and not body.join_existing:
        raise HTTPException(status_code=422, detail=f"Missing required fields: {', '.join(missing)}")
    if body.dup_score is not None and body.dup_score >= svc.app_config()["thresholds"]["likely_duplicate"] \
            and not body.join_existing and not (body.submit_anyway_reason or "").strip():
        raise HTTPException(status_code=422, detail="A reason is required to submit despite a likely duplicate")
    if isinstance(fields.get("data_sources"), list):
        fields["data_sources"] = ";".join(fields["data_sources"])
    fields["requester_email"] = email
    req = IntakeRequest(**{k: v for k, v in fields.items() if k in COLUMNS},
                        extra_fields={k: v for k, v in fields.items() if k not in COLUMNS},
                        dup_score=body.dup_score, dup_check_failed=body.dup_check_failed,
                        submit_anyway_reason=body.submit_anyway_reason,
                        duplicate_of=body.join_existing, status="merged" if body.join_existing else "submitted")
    start = time.perf_counter()
    try:
        req.category, req.category_confidence = svc.classify(ws, req.title, req.description)
    except Exception as e:  # the request is still saved; the pipeline classifies it again
        log.warning(f"ai_classify failed: {e}")
    classify_ms = int((time.perf_counter() - start) * 1000)
    session.add(req)
    session.flush()
    try:
        vec, _ = svc.embeddings.get_or_embed(ws, svc.normalize(req.title, req.description), query=False)
        svc.store_embedding(session, req.request_id, vec)
    except Exception as e:
        log.warning(f"embedding failed for {req.request_id}: {e}")
    session.commit()
    session.refresh(req)
    return _to_out(req, classify_ms)


@router.get("/requests/mine", response_model=list[RequestOut], operation_id="myRequests")
def my_requests(user_ws: Dependencies.UserClient, session: Dependencies.Session):
    email, _ = svc.identity(user_ws)
    stmt = select(IntakeRequest).where(IntakeRequest.requester_email == email) \
        .order_by(col(IntakeRequest.submitted_at).desc())
    return [_to_out(r) for r in session.exec(stmt)]


QUEUE_SQL = text("""
SELECT r.request_id, m.*
  FROM app.intake_requests r
  LEFT JOIN serving.request_embeddings e USING (request_id)
  LEFT JOIN LATERAL (
    SELECT * FROM (
      (SELECT p.source AS kind, p.project_key AS key, p.title, p.status, p.owner_email AS owner, p.business_unit,
              1 - (p.embedding <=> e.embedding) AS score
         FROM serving.projects_synced p WHERE p.project_key <> r.request_id
        ORDER BY p.embedding <=> e.embedding LIMIT 1)
      UNION ALL
      (SELECT 'request', o.request_id, o.title, o.status, o.requester_email, o.business_unit,
              1 - (oe.embedding <=> e.embedding)
         FROM serving.request_embeddings oe JOIN app.intake_requests o USING (request_id)
        WHERE o.request_id <> r.request_id AND o.status <> 'rejected'
        ORDER BY oe.embedding <=> e.embedding LIMIT 1)) c
    ORDER BY score DESC LIMIT 1) m ON e.embedding IS NOT NULL
 WHERE r.status IN ('submitted', 'in_review')
""")


@router.get("/review/queue", response_model=list[ReviewItemOut], operation_id="reviewQueue")
def review_queue(user_ws: Dependencies.UserClient, session: Dependencies.Session):
    svc.require_task_force(svc.identity(user_ws)[1])
    matches = {row["request_id"]: row for row in session.execute(QUEUE_SQL).mappings()}
    stmt = select(IntakeRequest).where(col(IntakeRequest.status).in_(["submitted", "in_review"])) \
        .order_by(col(IntakeRequest.submitted_at).desc())
    out = []
    for r in session.exec(stmt):
        m = matches.get(r.request_id)
        top = svc.to_match(m) if m and m["key"] else None
        out.append(ReviewItemOut(**_to_out(r).model_dump(), description=r.description, top_match=top))
    return out


@router.post("/review/{request_id}", response_model=ReviewOut, operation_id="reviewRequest")
def review_request(request_id: str, body: ReviewIn, user_ws: Dependencies.UserClient,
                   session: Dependencies.Session):
    email, groups = svc.identity(user_ws)
    svc.require_task_force(groups)
    req = session.get(IntakeRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if body.action == "merge" and not body.merged_into:
        raise HTTPException(status_code=422, detail="merged_into is required for a merge")
    req.status = {"approve": "approved", "merge": "merged", "reject": "rejected"}[body.action]
    if body.action == "merge":
        req.duplicate_of = body.merged_into
    req.updated_at = datetime.now(timezone.utc)
    session.add(req)
    decision = ReviewDecision(request_id=request_id, reviewer_email=email, action=body.action,
                              merged_into=body.merged_into, reason=body.reason)
    session.add(decision)
    session.commit()
    session.refresh(decision)
    return ReviewOut(decision_id=decision.decision_id, request_id=request_id, action=body.action, status=req.status)


@router.get("/portfolio/summary", response_model=PortfolioOut, operation_id="portfolioSummary")
def portfolio_summary(ws: Dependencies.Client, user_ws: Dependencies.UserClient):
    """KPIs from gold.portfolio_metrics, queried as the user so the business-unit row filter applies."""
    row = svc.portfolio_kpis(user_ws)
    space = os.environ.get("GENIE_SPACE_ID")
    url = f"{ws.config.host.rstrip('/')}/genie/rooms/{space}" if space else None
    return PortfolioOut(**row, genie_url=url)
