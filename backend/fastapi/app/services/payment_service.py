from sqlalchemy.orm import Session

from app.models.payment_method import PaymentMethod


class PaymentService:
    def __init__(self, db: Session):
        self.db = db

    def list_methods(self, user_id: str) -> list[PaymentMethod]:
        return self.db.query(PaymentMethod).filter(PaymentMethod.user_id == user_id).all()
