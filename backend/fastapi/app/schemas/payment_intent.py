from pydantic import BaseModel, ConfigDict, Field


class PaymentIntentPayload(BaseModel):
    model_config = ConfigDict(strict=True)

    task_id: str = Field(min_length=1)
    amount: float = Field(gt=0)
    currency: str = Field(min_length=3, max_length=8)
