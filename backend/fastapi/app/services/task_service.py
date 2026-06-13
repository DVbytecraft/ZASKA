from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.task_application import TaskApplication
from app.models.user_address import UserAddress
from app.models.kyc import KycSubmission
from app.models.user import User


class TaskService:
    def __init__(self, db: Session):
        self.db = db

    # ─── Tasks ──────────────────────────────────────────────────────────────

    def find_by_idempotency_key(self, key: str) -> Task | None:
        return self.db.execute(
            select(Task).where(Task.idempotency_key == key)
        ).scalars().one_or_none()

    def create_task(self, payload: dict, *, commit: bool = True) -> Task:
        lat = float(payload["latitude"])
        lon = float(payload["longitude"])
        if not (-90.0 <= lat <= 90.0):
            raise ValueError(f"Invalid latitude {lat}")
        if not (-180.0 <= lon <= 180.0):
            raise ValueError(f"Invalid longitude {lon}")
        service_category = (payload.get("service_category") or "TASK").upper()
        base_price = Decimal(str(payload["price"]))
        is_urgent = bool(payload.get("is_urgent", False))
        final_price = (base_price * Decimal("1.20")).quantize(Decimal("0.000001")) if is_urgent else base_price
        auto_release_minutes = 20 if service_category == "FOOD_DELIVERY" else 180
        task = Task(
            title=payload.get("title") or payload["description"][:60],
            description=payload["description"],
            price=final_price,
            currency=payload["currency"].upper(),
            latitude=lat,
            longitude=lon,
            address=payload.get("address"),
            mode=payload.get("mode") or "fast",
            service_category=service_category,
            is_urgent=is_urgent,
            escrow_auto_release_minutes=auto_release_minutes,
            status=payload.get("status", "OPEN"),
            created_by=payload["created_by"],
            stops=payload.get("stops"),
            scheduled_at=payload.get("scheduled_at"),
            any_schedule=bool(payload.get("any_schedule", False)),
            idempotency_key=payload.get("idempotency_key") or None,
            city=payload.get("city") or None,
            country=payload.get("country") or None,
        )
        self.db.add(task)
        if commit:
            self.db.commit()
            self.db.refresh(task)
        else:
            self.db.flush()
        return task

    def get_task(self, task_id: str) -> Task | None:
        return self.db.execute(
            select(Task).where(Task.id == task_id)
        ).scalars().one_or_none()

    def update_task(self, task_id: str, changes: dict) -> Task:
        # FOR UPDATE: prevents two concurrent admin edits on the same task
        # from reading stale state and both writing conflicting values.
        task = self.db.execute(
            select(Task).where(Task.id == task_id).with_for_update()
        ).scalars().one()
        for key, value in changes.items():
            if value is not None and hasattr(task, key):
                setattr(task, key, value)
        self.db.commit()
        self.db.refresh(task)
        return task

    def delete_task(self, task_id: str) -> None:
        from app.models.chat_message import ChatMessage
        from app.models.task_application import TaskApplication
        from app.models.wallet import Escrow

        # FOR UPDATE on escrow: closes TOCTOU window between the "no active escrow"
        # check and the actual deletion. Without the lock, a concurrent create_escrow
        # could succeed between these two operations, leaving an orphaned funded escrow.
        active = self.db.execute(
            select(Escrow)
            .where(Escrow.task_id == task_id, Escrow.status.in_(["funded", "hold"]))
            .with_for_update()
        ).scalars().first()
        if active:
            raise ValueError("Impossible de supprimer une tâche avec un paiement actif (escrow)")
        self.db.execute(
            ChatMessage.__table__.delete().where(ChatMessage.task_id == task_id)
        )
        self.db.execute(
            TaskApplication.__table__.delete().where(TaskApplication.task_id == task_id)
        )
        task = self.db.execute(
            select(Task).where(Task.id == task_id)
        ).scalars().one()
        self.db.delete(task)  # NegotiationEvent already has ondelete=CASCADE
        self.db.commit()

    def get_user_applications(self, user_id: str) -> list[TaskApplication]:
        return self.db.execute(
            select(TaskApplication)
            .where(TaskApplication.tasker_id == user_id)
            .order_by(TaskApplication.created_at.desc())
        ).scalars().all()

    # Progressive radius steps: 10 km → 50 km → 200 km → unlimited
    _RADIUS_STEPS = [10.0, 50.0, 200.0]
    _MIN_RESULTS_PER_RADIUS = 5

    def list_tasks(
        self,
        status: str | None = None,
        created_by: str | None = None,
        assigned_to: str | None = None,
        ref_lat: float | None = None,
        ref_lng: float | None = None,
        radius_km: float | None = None,
        country: str | None = None,
        city: str | None = None,
        limit: int = 500,
    ) -> tuple[list[Task], list[float | None]]:
        """Return (tasks, distances_km) sorted by proximity with automatic radius expansion.

        limit default 500: prevents unbounded memory load when the task table grows large.
        At 100k tasks, loading all without a limit would OOM the API pod.
        """
        stmt = select(Task)
        if status:
            stmt = stmt.where(Task.status == status.upper())
        if created_by:
            stmt = stmt.where(Task.created_by == created_by)
        if assigned_to:
            stmt = stmt.where(Task.assigned_to == assigned_to)
        if country:
            stmt = stmt.where(Task.country.ilike(f"%{country.strip()}%"))
        if city:
            stmt = stmt.where(Task.city.ilike(f"%{city.strip()}%"))

        if ref_lat is not None and ref_lng is not None:
            if radius_km is not None:
                radii_to_try = [radius_km, None]
            else:
                radii_to_try = list(self._RADIUS_STEPS) + [None]

            tasks: list[Task] = []
            for r in radii_to_try:
                q = stmt
                if r is not None:
                    import math
                    lat_delta = r / 111.0
                    lng_delta = r / (111.0 * max(math.cos(math.radians(ref_lat)), 0.01))
                    q = q.where(
                        Task.latitude.between(ref_lat - lat_delta, ref_lat + lat_delta),
                        Task.longitude.between(ref_lng - lng_delta, ref_lng + lng_delta),
                    )
                tasks = self.db.execute(
                    q.order_by(Task.created_at.desc()).limit(limit)
                ).scalars().all()
                if r is None:
                    break
                tasks = [
                    t for t in tasks
                    if t.latitude and t.longitude
                    and self._haversine(ref_lat, ref_lng, t.latitude, t.longitude) <= r
                ]
                if len(tasks) >= self._MIN_RESULTS_PER_RADIUS:
                    break

            def _dist(t: Task) -> float:
                if t.latitude and t.longitude:
                    return self._haversine(ref_lat, ref_lng, t.latitude, t.longitude)
                return float("inf")

            tasks.sort(key=_dist)
            distances: list[float | None] = [
                self._haversine(ref_lat, ref_lng, t.latitude, t.longitude)
                if (t.latitude and t.longitude) else None
                for t in tasks
            ]
            return tasks, distances

        tasks = self.db.execute(
            stmt.order_by(Task.created_at.desc()).limit(limit)
        ).scalars().all()
        return tasks, [None] * len(tasks)

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        import math
        R = 6371.0
        d_lat = math.radians(lat2 - lat1)
        d_lon = math.radians(lon2 - lon1)
        a = (math.sin(d_lat / 2) ** 2
             + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def update_status(self, task_id: str, status: str) -> Task:
        # Callers from the router already hold a FOR UPDATE lock on this task.
        # This method executes inside the same transaction — no second lock needed.
        task = self.db.execute(
            select(Task).where(Task.id == task_id)
        ).scalars().one()
        task.status = status
        self.db.commit()
        self.db.refresh(task)
        return task

    def negotiate(self, task_id: str, proposed_budget: Decimal) -> Task:
        task = self.db.execute(
            select(Task).where(Task.id == task_id)
        ).scalars().one()
        task.price = proposed_budget
        self.db.commit()
        self.db.refresh(task)
        return task

    def propose_price(self, task_id: str, proposer_id: str, proposed_price: Decimal) -> Task:
        """Executor proposes a new price. Sets negotiation_status='pending'."""
        task = self.db.execute(
            select(Task).where(Task.id == task_id)
        ).scalars().one()
        if task.original_price is None:
            task.original_price = task.price
        task.negotiated_price = proposed_price
        task.negotiated_by = proposer_id
        task.negotiation_status = "pending"
        self.db.commit()
        self.db.refresh(task)
        return task

    def accept_negotiation(self, task_id: str, *, commit: bool = True) -> Task:
        """Client accepts the proposed price — updates task.price to negotiated_price."""
        task = self.db.execute(
            select(Task).where(Task.id == task_id)
        ).scalars().one()
        if task.negotiated_price:
            task.price = task.negotiated_price
        task.negotiation_status = "accepted"
        if commit:
            self.db.commit()
            self.db.refresh(task)
        else:
            self.db.flush()
        return task

    def reject_negotiation(self, task_id: str, *, commit: bool = True) -> Task:
        """Reject the proposed price — resets to 'none' so a new round can start."""
        task = self.db.execute(
            select(Task).where(Task.id == task_id)
        ).scalars().one()
        task.negotiation_status = "none"
        task.negotiated_price = None
        task.negotiated_by = None
        if commit:
            self.db.commit()
            self.db.refresh(task)
        else:
            self.db.flush()
        return task

    def cancel_task(self, task_id: str, new_status: str) -> Task:
        """Cancel an assigned/active task. new_status is OPEN (republish) or CANCELLED."""
        task = self.db.execute(
            select(Task).where(Task.id == task_id)
        ).scalars().one()
        task.status = new_status
        task.assigned_to = None
        task.negotiation_status = "none"
        task.negotiated_price = None
        task.negotiated_by = None
        self.db.commit()
        self.db.refresh(task)
        return task

    def abandon_and_republish(self, task_id: str) -> Task:
        """Executor abandons after price rejection — task goes back to OPEN."""
        task = self.db.execute(
            select(Task).where(Task.id == task_id)
        ).scalars().one()
        task.status = "OPEN"
        task.assigned_to = None
        task.negotiation_status = "none"
        task.negotiated_price = None
        task.negotiated_by = None
        self.db.commit()
        self.db.refresh(task)
        return task

    def set_completion_percent(self, task_id: str, completion_percent: int) -> Task:
        # Superseded by mark_pending_validation (atomic status + pct in one commit).
        # Kept for backward compatibility with any direct callers.
        task = self.db.execute(
            select(Task).where(Task.id == task_id)
        ).scalars().one()
        task.completion_percent = completion_percent
        self.db.commit()
        self.db.refresh(task)
        return task

    def rate_task(self, task_id: str, score: int, rater_id: str) -> Task:
        """Legacy wrapper kept for compatibility with simple client→tasker rating flows."""
        from app.services.rating_service import RatingService

        RatingService(self.db).submit_client_review(
            task_id=task_id,
            client_user_id=rater_id,
            punctuality_score=score,
            quality_score=score,
            communication_score=score,
            standards_score=score,
            comment=None,
        )
        return self.db.execute(
            select(Task).where(Task.id == task_id)
        ).scalars().one()

    def mark_pending_validation(
        self, task_id: str, tasker_id: str, pct: int, proof_url: str | None = None
    ) -> Task:
        """Atomically set completion_percent + status=PENDING_VALIDATION in one commit.

        P1-003 FIX: Uses FOR UPDATE to prevent concurrent completion declarations.
        """
        task = self.db.execute(
            select(Task).where(Task.id == task_id).with_for_update()
        ).scalars().one()
        if task.assigned_to != tasker_id:
            raise ValueError("Non autorisé")
        if task.status != "ASSIGNED":
            raise ValueError(
                f"La tâche doit être ASSIGNED pour être déclarée terminée (statut: {task.status})"
            )
        task.completion_percent = pct
        task.status = "PENDING_VALIDATION"
        if proof_url:
            task.proof_photo_url = proof_url
        self.db.commit()
        self.db.refresh(task)
        return task

    def tasker_abandon(self, task_id: str, tasker_id: str) -> Task:
        """Assigned tasker abandons the task — returns it to OPEN, resets assignment.

        P1-002 FIX: FOR UPDATE prevents concurrent double-abandon (TOCTOU race).
        """
        task = self.db.execute(
            select(Task).where(Task.id == task_id).with_for_update()
        ).scalars().one()
        if task.assigned_to != tasker_id:
            raise ValueError("Non autorisé")
        if task.status not in ("ASSIGNED", "PAUSED"):
            raise ValueError("L'abandon n'est possible que sur une tâche ASSIGNED ou PAUSED")
        task.status = "OPEN"
        task.assigned_to = None
        task.negotiation_status = "none"
        task.negotiated_price = None
        task.negotiated_by = None
        self.db.commit()
        self.db.refresh(task)
        return task

    def match_tasks(self, latitude: float, longitude: float, radius_km: float) -> list[Task]:
        if not (-90.0 <= latitude <= 90.0):
            raise ValueError(f"Invalid latitude {latitude}: must be between -90 and 90")
        if not (-180.0 <= longitude <= 180.0):
            raise ValueError(f"Invalid longitude {longitude}: must be between -180 and 180")
        if radius_km <= 0 or radius_km > 500:
            raise ValueError(f"Invalid radius {radius_km} km: must be between 0 and 500")
        radius_m = radius_km * 1000
        sql = text(
            """
            SELECT id FROM tasks
            WHERE ST_DWithin(
                ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography,
                ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography,
                :radius_m
            )
            ORDER BY created_at DESC
            LIMIT 500
            """
        )
        rows = self.db.execute(sql, {"longitude": longitude, "latitude": latitude, "radius_m": radius_m}).mappings().all()
        ids = [r["id"] for r in rows]
        if not ids:
            return []
        return self.db.execute(
            select(Task).where(Task.id.in_(ids))
        ).scalars().all()

    # ─── Applications (Choose Mode) ─────────────────────────────────────────

    def count_pending_applications(self, task_id: str) -> int:
        from sqlalchemy import func
        result = self.db.execute(
            select(func.count()).select_from(TaskApplication).where(
                TaskApplication.task_id == task_id,
                TaskApplication.status == "pending",
            )
        ).scalar_one()
        return result

    def apply_task(
        self,
        task_id: str,
        tasker_id: str,
        proposed_price: Decimal | None,
        currency: str,
        message: str | None,
    ) -> TaskApplication:
        application = TaskApplication(
            task_id=task_id,
            tasker_id=tasker_id,
            proposed_price=proposed_price,
            currency=currency,
            status="pending",
            message=message,
        )
        self.db.add(application)
        # IntegrityError (duplicate) propagates to the router → HTTP 409.
        self.db.flush()
        return application

    def list_applications(self, task_id: str) -> list[tuple[TaskApplication, User]]:
        return self.db.execute(
            select(TaskApplication, User)
            .join(User, User.id == TaskApplication.tasker_id)
            .where(TaskApplication.task_id == task_id)
            .order_by(TaskApplication.created_at.asc())
        ).all()

    def list_available_taskers_for_task(self, task_id: str, limit: int = 25) -> list[dict]:
        task = self.db.execute(
            select(Task).where(Task.id == task_id)
        ).scalars().one()

        taskers = self.db.execute(
            select(User).where(
                User.role == "tasker",
                User.is_verified.is_(True),
                User.is_suspended.is_(False),
                User.is_locked.is_(False),
            )
        ).scalars().all()
        if not taskers:
            return []

        tasker_ids = [item.id for item in taskers]
        addresses = self.db.execute(
            select(UserAddress)
            .where(UserAddress.user_id.in_(tasker_ids))
            .order_by(UserAddress.user_id.asc(), UserAddress.is_default.desc(), UserAddress.created_at.desc())
        ).scalars().all()
        latest_kyc_rows = self.db.execute(
            select(KycSubmission)
            .where(KycSubmission.user_id.in_(tasker_ids))
            .order_by(KycSubmission.user_id.asc(), KycSubmission.created_at.desc())
        ).scalars().all()

        addr_map: dict[str, list[UserAddress]] = {}
        for addr in addresses:
            addr_map.setdefault(addr.user_id, []).append(addr)

        latest_kyc: dict[str, KycSubmission] = {}
        for row in latest_kyc_rows:
            latest_kyc.setdefault(row.user_id, row)

        results: list[dict] = []
        for user in taskers:
            kyc = latest_kyc.get(user.id)
            security_ready = bool(
                user.tasker_security_verified
                and user.biometric_enabled
                and user.criminal_record_status in {"clear", "approved"}
                and kyc is not None
                and kyc.status == "approved"
                and not kyc.is_expired
                and getattr(kyc, "biometric_status", "pending") in {"approved", "clear"}
                and getattr(kyc, "criminal_record_status", "pending") in {"approved", "clear"}
                and getattr(kyc, "criminal_record_risk_level", "pending") in {"approved", "clear", "low"}
            )
            if not security_ready:
                continue

            best_distance: float | None = None
            match_reason = "country_profile"
            best_city = getattr(user, "city", None)
            best_country = getattr(user, "country_code", None)

            for addr in addr_map.get(user.id, []):
                if addr.latitude is not None and addr.longitude is not None:
                    distance = self._haversine(task.latitude, task.longitude, addr.latitude, addr.longitude)
                    if best_distance is None or distance < best_distance:
                        best_distance = distance
                        best_city = addr.city
                        best_country = addr.country
                        match_reason = "nearby_address"
                elif task.city and addr.city and addr.city.strip().lower() == task.city.strip().lower():
                    best_city = addr.city
                    best_country = addr.country
                    if best_distance is None:
                        match_reason = "same_city"

            if best_distance is None and task.city and best_city and best_city.strip().lower() == task.city.strip().lower():
                match_reason = "same_city"

            rating_avg = round(user.rating_sum / user.rating_count, 2) if user.rating_count > 0 else None
            results.append(
                {
                    "id": user.id,
                    "firstName": user.first_name,
                    "lastName": user.last_name,
                    "fullName": user.full_name,
                    "avatarUrl": user.avatar_url,
                    "city": best_city,
                    "country": best_country,
                    "countryCode": user.country_code,
                    "availability": getattr(user, "availability", None),
                    "hourlyRate": getattr(user, "hourly_rate", None),
                    "responseTime": getattr(user, "response_time", None),
                    "ratingAverage": rating_avg,
                    "ratingCount": user.rating_count,
                    "distanceKm": round(best_distance, 1) if best_distance is not None else None,
                    "matchReason": match_reason,
                    "taskerSecurityVerified": user.tasker_security_verified,
                    "biometricEnabled": user.biometric_enabled,
                    "criminalRecordStatus": user.criminal_record_status,
                    "kycStatus": getattr(kyc, "status", None),
                    "kycExpiresAt": kyc.expires_at.isoformat() if kyc and kyc.expires_at else None,
                }
            )

        results.sort(
            key=lambda item: (
                item["distanceKm"] is None,
                item["distanceKm"] if item["distanceKm"] is not None else 999999,
                item["ratingAverage"] is None,
                -(item["ratingAverage"] or 0),
                -(item["ratingCount"] or 0),
            )
        )
        return results[:limit]

    def accept_task(self, task_id: str, tasker_id: str) -> Task:
        """Fast Mode: tasker self-assigns. Choose Mode: client assigns a specific tasker."""
        task = self.db.execute(
            select(Task).where(Task.id == task_id).with_for_update()
        ).scalars().one()
        if task.status != "OPEN":
            raise ValueError(f"Task {task_id} is no longer open (status: {task.status})")
        task.assigned_to = tasker_id
        task.status = "ASSIGNED"
        self.db.execute(
            TaskApplication.__table__.update()
            .where(TaskApplication.task_id == task_id)
            .values(status="rejected")
        )
        self.db.execute(
            TaskApplication.__table__.update()
            .where(
                TaskApplication.task_id == task_id,
                TaskApplication.tasker_id == tasker_id,
            )
            .values(status="accepted")
        )
        self.db.commit()
        self.db.refresh(task)
        return task
