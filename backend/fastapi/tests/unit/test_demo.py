from decimal import Decimal


def test_create_demo_session_returns_token_and_seeded_wallet(client, db):
    from app.models.user import User
    from app.models.wallet import Transaction, Wallet

    response = client.post("/api/demo/session", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True

    data = payload["data"]
    assert data["accessToken"]
    assert data["currency"] == "EUR"
    assert data["country"] == "FR"
    assert data["isDemo"] is True

    user = db.get(User, data["userId"])
    assert user is not None
    assert user.is_demo is True

    wallet = db.query(Wallet).filter(
        Wallet.user_id == data["userId"],
        Wallet.currency == "EUR",
    ).one()
    assert wallet.balance == Decimal("500")

    tx = db.query(Transaction).filter(
        Transaction.wallet_id == wallet.id,
        Transaction.reference.like("demo_seed_%"),
    ).one()
    assert tx.type == "credit"
    assert tx.amount == Decimal("500")
    assert tx.status == "completed"
