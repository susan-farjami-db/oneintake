"""OBO proxy for the portfolio Genie space. Queries run as the signed-in user."""

import os

from fastapi import HTTPException

from .core import Dependencies, create_router
from .models import GenieAskIn, GenieAskOut, GenieConfigOut

router = create_router()

QUESTIONS = [
    "What is the backlog value by business unit?",
    "How many requests have been waiting more than 30 days?",
    "What is the duplicate rate by month?",
    "What are the top 5 requests by estimated value that are still in review?",
]


def _space() -> str:
    space = os.environ.get("GENIE_SPACE_ID") or ""
    if not space:
        raise HTTPException(status_code=503, detail="Genie is not configured")
    return space


def _text(msg) -> str:
    parts = []
    for a in msg.attachments or []:
        if getattr(a, "text", None) and a.text.content:
            parts.append(a.text.content)
        if getattr(a, "query", None) and a.query.description:
            parts.append(a.query.description)
    return "\n".join(parts).strip() or (getattr(msg, "content", None) or "")


def _ask(user_ws, question: str, conversation_id: str | None) -> GenieAskOut:
    space = _space()
    try:
        if conversation_id:
            msg = user_ws.genie.create_message_and_wait(space, conversation_id, question)
        else:
            msg = user_ws.genie.start_conversation_and_wait(space, question)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Genie failed: {e}") from e
    cid = msg.conversation_id
    att = next((a for a in (msg.attachments or []) if a.query), None)
    if not att:
        return GenieAskOut(conversation_id=cid, answer=_text(msg) or "Genie returned no SQL for that question.")
    try:
        res = user_ws.genie.get_message_attachment_query_result(space, cid, msg.message_id, att.attachment_id)
    except Exception as e:
        return GenieAskOut(conversation_id=cid, answer=_text(msg) or str(e), sql=att.query.query)
    stmt = res.statement_response
    cols = [c.name for c in (stmt.manifest.schema.columns if stmt and stmt.manifest and stmt.manifest.schema else [])]
    data = (stmt.result.data_array if stmt and stmt.result else None) or []
    rows = [[("" if v is None else str(v)) for v in row] for row in data[:50]]
    sql = att.query.query
    answer = _text(msg) or ("No rows." if not rows else f"{len(rows)} row{'s' if len(rows) != 1 else ''}.")
    return GenieAskOut(conversation_id=cid, answer=answer, sql=sql, columns=cols, rows=rows)


@router.get("/genie/config", response_model=GenieConfigOut, operation_id="genieConfig")
def genie_config():
    return GenieConfigOut(configured=bool(os.environ.get("GENIE_SPACE_ID")), questions=QUESTIONS)


@router.post("/genie/ask", response_model=GenieAskOut, operation_id="askGenie")
def ask_genie(body: GenieAskIn, user_ws: Dependencies.UserClient):
    q = (body.question or "").strip()
    if not q:
        raise HTTPException(status_code=422, detail="Question is required")
    return _ask(user_ws, q, body.conversation_id)
