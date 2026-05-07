from pydantic import BaseModel, ConfigDict


class PaymentMethodResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    id: str
    type: str
    details: str
    isDefault: bool
