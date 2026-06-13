from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.core.security import create_token
from app.models.kyc import KycSubmission
from app.models.task import Task
from app.models.user import User
from app.models.user_address import UserAddress
from app.services.country_rollout_service import CountryRolloutService
from app.services.module_control_service import ModuleControlService
from app.services.task_service import TaskService
from app.services.wallet_service import WalletService


def _headers_for(user_id: str) -> dict[str, str]:
    token = create_token(user_id, timedelta(minutes=30), "access")
    return {"Authorization": f"Bearer {token}"}


def _seed_runtime(db) -> None:
    CountryRolloutService(db).ensure_country("TG")
    ModuleControlService(db).seed_catalog()


def _make_user(db, *, role: str, email: str | None = None, **extra) -> User:
    user = User(
        id=str(uuid.uuid4()),
        email=email or f"{role}-{uuid.uuid4().hex[:8]}@zaska.test",
        role=role,
        is_verified=True,
        country_code="TG",
        first_name=extra.pop("first_name", role.title()),
        last_name=extra.pop("last_name", "User"),
        full_name=extra.pop("full_name", f"{role.title()} User"),
        **extra,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_security_ready_tasker(db, *, city: str = "Lome", lat: float = 6.1319, lng: float = 1.2228) -> User:
    tasker = _make_user(
        db,
        role="tasker",
        first_name="Ready",
        last_name="Tasker",
        full_name="Ready Tasker",
        tasker_security_verified=True,
        biometric_enabled=True,
        criminal_record_status="clear",
        city=city,
        availability="available",
        hourly_rate=12.5,
        response_time="5 min",
        rating_sum=18.0,
        rating_count=4,
    )
    now = datetime.now(timezone.utc)
    db.add(
        KycSubmission(
            user_id=tasker.id,
            id_document_url="https://example.test/id-front.jpg",
            id_document_back_url="https://example.test/id-back.jpg",
            selfie_url="https://example.test/selfie.jpg",
            biometric_selfie_url="https://example.test/biometric.jpg",
            criminal_record_url="https://example.test/casier.pdf",
            status="approved",
            biometric_status="approved",
            criminal_record_status="approved",
            criminal_record_risk_level="low",
            approved_at=now,
            expires_at=now + timedelta(days=365),
            criminal_record_issued_at=now,
            criminal_record_expires_at=now + timedelta(days=365),
        )
    )
    db.add(
        UserAddress(
            user_id=tasker.id,
            label="Maison",
            street="Quartier Administratif",
            city=city,
            country="Togo",
            latitude=lat,
            longitude=lng,
            is_default=True,
        )
    )
    db.commit()
    db.refresh(tasker)
    return tasker


def _create_task(db, *, creator_id: str, price: Decimal = Decimal("100")) -> Task:
    return TaskService(db).create_task(
        {
            "title": "Courses de quartier",
            "description": "Livrer quelques articles au client",
            "price": str(price),
            "currency": "EUR",
            "latitude": 6.1319,
            "longitude": 1.2228,
            "address": "Lomé centre",
            "city": "Lome",
            "country": "Togo",
            "created_by": creator_id,
        }
    )


def test_available_taskers_endpoint_returns_only_security_ready_taskers(client, db):
    _seed_runtime(db)
    creator = _make_user(db, role="client", first_name="Client", last_name="Owner", full_name="Client Owner")
    ready_tasker = _make_security_ready_tasker(db)
    _make_user(
        db,
        role="tasker",
        first_name="Blocked",
        last_name="Tasker",
        full_name="Blocked Tasker",
        city="Lome",
        availability="offline",
        hourly_rate=10.0,
        response_time="30 min",
    )
    task = _create_task(db, creator_id=creator.id)

    response = client.get(f"/api/tasks/{task.id}/available-taskers", headers=_headers_for(creator.id))

    assert response.status_code == 200
    payload = response.json()["data"]
    assert len(payload) == 1
    assert payload[0]["id"] == ready_tasker.id
    assert payload[0]["matchReason"] in {"nearby_address", "same_city", "country_profile"}
    assert payload[0]["taskerSecurityVerified"] is True
    assert payload[0]["kycStatus"] == "approved"


def test_task_timeline_endpoint_tracks_assignment_completion_and_confirmation(client, db):
    _seed_runtime(db)
    creator = _make_user(db, role="client", first_name="Alice", last_name="Client", full_name="Alice Client")
    tasker = _make_security_ready_tasker(db)

    create_response = client.post(
        "/api/tasks",
        headers=_headers_for(creator.id),
        json={
            "title": "Aide à domicile",
            "description": "Aider pour une tâche rapide",
            "price": 50,
            "currency": "EUR",
            "latitude": 6.1319,
            "longitude": 1.2228,
            "address": "Lomé",
            "city": "Lome",
            "country": "Togo",
        },
    )
    assert create_response.status_code == 200
    task_id = create_response.json()["data"]["id"]

    accept_response = client.post(
        f"/api/tasks/{task_id}/accept",
        headers=_headers_for(creator.id),
        json={"tasker_id": tasker.id},
    )
    assert accept_response.status_code == 200

    task = db.get(Task, task_id)
    assert task is not None
    task.created_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    db.commit()

    complete_response = client.post(
        f"/api/tasks/{task_id}/complete",
        headers=_headers_for(tasker.id),
        json={"partial": False, "completion_percent": 100},
    )
    assert complete_response.status_code == 200

    confirm_response = client.post(
        f"/api/tasks/{task_id}/confirm",
        headers=_headers_for(creator.id),
    )
    assert confirm_response.status_code == 200

    timeline_response = client.get(
        f"/api/tasks/{task_id}/timeline",
        headers=_headers_for(creator.id),
    )
    assert timeline_response.status_code == 200
    event_types = [item["eventType"] for item in timeline_response.json()["data"]]

    assert "created" in event_types
    assert "assigned" in event_types
    assert "completion_declared" in event_types
    assert "confirmed" in event_types


def test_posted_and_received_tasks_are_visible_to_the_right_users(client, db):
    _seed_runtime(db)
    creator = _make_user(db, role="client", first_name="Poster", last_name="Client", full_name="Poster Client")
    tasker = _make_security_ready_tasker(db)
    task = _create_task(db, creator_id=creator.id, price=Decimal("80"))
    TaskService(db).accept_task(task.id, tasker.id)

    mine_response = client.get("/api/tasks?mine=true", headers=_headers_for(creator.id))
    assert mine_response.status_code == 200
    mine_ids = {item["id"] for item in mine_response.json()["data"]}
    assert task.id in mine_ids

    received_response = client.get("/api/tasks?assigned_to_me=true", headers=_headers_for(tasker.id))
    assert received_response.status_code == 200
    received_payload = received_response.json()["data"]
    received_ids = {item["id"] for item in received_payload}
    assert task.id in received_ids
    received_task = next(item for item in received_payload if item["id"] == task.id)
    assert received_task["assignedTo"] == tasker.id
    assert received_task["status"] == "ASSIGNED"


def test_negotiation_accept_rejects_when_client_cannot_top_up_escrow(client, db):
    _seed_runtime(db)
    creator = _make_user(db, role="client", first_name="Budget", last_name="Client", full_name="Budget Client")
    tasker = _make_security_ready_tasker(db)
    task = _create_task(db, creator_id=creator.id, price=Decimal("100"))
    TaskService(db).accept_task(task.id, tasker.id)

    wallet_service = WalletService(db)
    wallet_service.create_wallet(creator.id, "EUR")
    wallet_service.credit_wallet(creator.id, "EUR", Decimal("100"), reference=f"seed:{uuid.uuid4().hex}")
    escrow = wallet_service.create_escrow(
        task_id=task.id,
        payer_id=creator.id,
        payee_id=tasker.id,
        amount=Decimal("100"),
        currency="EUR",
    )

    negotiate_response = client.post(
        f"/api/tasks/{task.id}/negotiate",
        headers=_headers_for(tasker.id),
        json={"proposed_price": 150},
    )
    assert negotiate_response.status_code == 200

    respond_response = client.post(
        f"/api/tasks/{task.id}/negotiate/respond",
        headers=_headers_for(creator.id),
        json={"accept": True},
    )
    assert respond_response.status_code == 409

    db.refresh(task)
    db.refresh(escrow)
    assert str(task.price) == "100.000000"
    assert task.negotiation_status == "pending"
    assert str(escrow.amount) == "100.000000"
