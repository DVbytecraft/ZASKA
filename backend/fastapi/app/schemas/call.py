from typing import Literal

from pydantic import BaseModel


class InitiateCallRequest(BaseModel):
    task_id: str
    media_type: Literal["audio", "video"]


class WsTicketResponse(BaseModel):
    ticket: str
