from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chat_message import ChatMessage
from app.models.task import Task


class ChatService:
    def __init__(self, db: Session):
        self.db = db

    def assert_participant(self, task_id: str, user_id: str) -> None:
        task = self.db.execute(
            select(Task).where(Task.id == task_id)
        ).scalars().one_or_none()
        if task is None:
            raise LookupError("Task not found")
        if task.created_by != user_id and task.assigned_to != user_id:
            raise PermissionError("Not a participant in this task")

    def create_message(
        self,
        task_id: str,
        sender_id: str,
        message: str,
        media_url: str | None = None,
        media_type: str | None = None,
    ) -> ChatMessage:
        msg = ChatMessage(
            task_id=task_id,
            sender_id=sender_id,
            message=message,
            media_url=media_url,
            media_type=media_type,
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def list_messages(self, task_id: str, limit: int = 200) -> list[ChatMessage]:
        return self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.task_id == task_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
        ).scalars().all()
