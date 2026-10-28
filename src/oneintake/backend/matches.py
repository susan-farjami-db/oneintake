"""Full detail for one duplicate match, so the requester can review it before Join existing."""

from fastapi import HTTPException
from sqlmodel import text

from .core import Dependencies, create_router
from .models import MatchDetailOut

router = create_router()

# A match key is either a live request_id (app.intake_requests) or a synced project_key
# (serving.projects_synced, which also carries historical requests under source='request').
DETAIL_SQL = text("""
(SELECT 'request' AS kind, request_id AS key, title, description, status,
        requester_email AS owner, business_unit, est_value_usd, category, submitted_at AS updated_at
   FROM app.intake_requests WHERE request_id = :key)
UNION ALL
(SELECT source, project_key, title, description, status, owner_email, business_unit,
        est_value_usd, category, synced_at AS updated_at
   FROM serving.projects_synced WHERE project_key = :key)
LIMIT 1
""")


@router.get("/matches/{key}", response_model=MatchDetailOut, operation_id="matchDetail")
def match_detail(key: str, session: Dependencies.Session):
    row = session.execute(DETAIL_SQL, {"key": key}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Match not found")
    return MatchDetailOut(**row)
