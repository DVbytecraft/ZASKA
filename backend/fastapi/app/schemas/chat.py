from pydantic import BaseModel, ConfigDict, Field


class ChatMessagePayload(BaseModel):
    model_config = ConfigDict(strict=True)

    task_id: str = Field(min_length=1)
    message: str = Field(min_length=1, max_length=2000)
