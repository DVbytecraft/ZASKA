from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ChatMessagePayload(BaseModel):
    model_config = ConfigDict(strict=True)

    task_id: str = Field(min_length=1)
    message: str = Field(max_length=2000, default="")
    media_url: Optional[str] = Field(default=None, max_length=512)
    media_type: Optional[str] = Field(default=None, pattern=r"^(image|video|document)$")
