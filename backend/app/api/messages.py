import uuid

from fastapi import APIRouter, Response, status
from sqlalchemy.dialects.postgresql import insert

from app.api.deps import CurrentUser, DbSession
from app.core.errors import not_found
from app.models import ChatSession, Feedback, Message, MessageRole
from app.schemas.api import FeedbackCreate

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("/{message_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
async def feedback(
    message_id: uuid.UUID, body: FeedbackCreate, db: DbSession, user: CurrentUser
) -> Response:
    """Оценка ответа ассистента. Повторная оценка заменяет предыдущую."""
    message = await db.get(Message, message_id)
    session = await db.get(ChatSession, message.session_id) if message else None
    if (
        message is None
        or message.role != MessageRole.ASSISTANT
        or session is None
        or session.user_id != user.id
    ):
        raise not_found("message")

    stmt = insert(Feedback).values(
        message_id=message_id, user_id=user.id, score=body.score, comment=body.comment
    )
    await db.execute(
        stmt.on_conflict_do_update(
            constraint="uq_feedback_message_id",
            set_={"score": stmt.excluded.score, "comment": stmt.excluded.comment},
        )
    )
    await db.commit()
    # отправка score в Langfuse по message.trace_id — роль 5
    return Response(status_code=status.HTTP_204_NO_CONTENT)
