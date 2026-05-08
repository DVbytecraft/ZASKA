from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.task_application import TaskApplication
from app.models.user import User


class TaskService:
    def __init__(self, db: Session):
        self.db = db

    # ─── Tasks ──────────────────────────────────────────────────────────────

    def create_task(self, payload: dict) -> Task:
        lat = float(payload["latitude"])
        lon = float(payload["longitude"])
        if not (-90.0 <= lat <= 90.0):
            raise ValueError(f"Invalid latitude {lat}")
        if not (-180.0 <= lon <= 180.0):
            raise ValueError(f"Invalid longitude {lon}")
        task = Task(
            title=payload.get("title") or payload["description"][:60],
            description=payload["description"],
            price=Decimal(str(payload["price"])),
            currency=payload["currency"].upper(),
            latitude=payload["latitude"],
            longitude=payload["longitude"],
            address=payload.get("address"),
            status=payload.get("status", "OPEN"),
            created_by=payload["created_by"],
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def get_task(self, task_id: str) -> Task | None:
        return self.db.query(Task).filter(Task.id == task_id).one_or_none()

    def update_task(self, task_id: str, changes: dict) -> Task:
        task = self.db.query(Task).filter(Task.id == task_id).one()
        for key, value in changes.items():
            if value is not None and hasattr(task, key):
                setattr(task, key, value)
        self.db.commit()
        self.db.refresh(task)
        return task

    def delete_task(self, task_id: str) -> None:
        task = self.db.query(Task).filter(Task.id == task_id).one()
        self.db.delete(task)
        self.db.commit()

    def get_user_applications(self, user_id: str) -> list[TaskApplication]:
        return (
            self.db.query(TaskApplication)
            .filter(TaskApplication.tasker_id == user_id)
            .order_by(TaskApplication.created_at.desc())
            .all()
        )

    def list_tasks(
        self,
        status: str | None = None,
        created_by: str | None = None,
        assigned_to: str | None = None,
        ref_lat: float | None = None,
        ref_lng: float | None = None,
    ) -> tuple[list[Task], list[float | None]]:
        """Return (tasks, distances_km). distances are None when no ref provided."""
        query = self.db.query(Task)
        if status:
            query = query.filter(Task.status == status.upper())
        if created_by:
            query = query.filter(Task.created_by == created_by)
        if assigned_to:
            query = query.filter(Task.assigned_to == assigned_to)

        if ref_lat is not None and ref_lng is not None:
            # PostGIS: sort by distance from reference point, tasks with no coords go last.
            # Use bindparams — never interpolate user coords directly into SQL strings.
            order_expr = text(
                "ST_Distance("
                "ST_SetSRID(ST_MakePoint(tasks.longitude, tasks.latitude), 4326)::geography,"
                "ST_SetSRID(ST_MakePoint(:ref_lng, :ref_lat), 4326)::geography"
                ") ASC"
            ).bindparams(ref_lng=ref_lng, ref_lat=ref_lat)
            tasks = query.order_by(
                Task.latitude == 0,
                order_expr,
            ).all()
            distances: list[float | None] = []
            for t in tasks:
                if t.latitude and t.longitude and not (t.latitude == 0 and t.longitude == 0):
                    d = self._haversine(ref_lat, ref_lng, t.latitude, t.longitude)
                    distances.append(d)
                else:
                    distances.append(None)
            return tasks, distances

        tasks = query.order_by(Task.created_at.desc()).all()
        return tasks, [None] * len(tasks)

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        import math
        R = 6371.0
        d_lat = math.radians(lat2 - lat1)
        d_lon = math.radians(lon2 - lon1)
        a = math.sin(d_lat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def update_status(self, task_id: str, status: str) -> Task:
        task = self.db.query(Task).filter(Task.id == task_id).one()
        task.status = status
        self.db.commit()
        self.db.refresh(task)
        return task

    def negotiate(self, task_id: str, proposed_budget: Decimal) -> Task:
        task = self.db.query(Task).filter(Task.id == task_id).one()
        task.price = proposed_budget
        self.db.commit()
        self.db.refresh(task)
        return task

    def propose_price(self, task_id: str, proposer_id: str, proposed_price: Decimal) -> Task:
        """Executor proposes a new price. Sets negotiation_status='pending'."""
        task = self.db.query(Task).filter(Task.id == task_id).one()
        task.negotiated_price = proposed_price
        task.negotiated_by = proposer_id
        task.negotiation_status = "pending"
        self.db.commit()
        self.db.refresh(task)
        return task

    def accept_negotiation(self, task_id: str) -> Task:
        """Client accepts the proposed price — updates task.price to negotiated_price."""
        task = self.db.query(Task).filter(Task.id == task_id).one()
        if task.negotiated_price:
            task.price = task.negotiated_price
        task.negotiation_status = "accepted"
        self.db.commit()
        self.db.refresh(task)
        return task

    def reject_negotiation(self, task_id: str) -> Task:
        """Client rejects the proposed price."""
        task = self.db.query(Task).filter(Task.id == task_id).one()
        task.negotiation_status = "rejected"
        self.db.commit()
        self.db.refresh(task)
        return task

    def abandon_and_republish(self, task_id: str) -> Task:
        """Executor abandons after price rejection — task goes back to OPEN."""
        task = self.db.query(Task).filter(Task.id == task_id).one()
        task.status = "OPEN"
        task.assigned_to = None
        task.negotiation_status = "none"
        task.negotiated_price = None
        task.negotiated_by = None
        self.db.commit()
        self.db.refresh(task)
        return task

    def set_completion_percent(self, task_id: str, completion_percent: int) -> Task:
        task = self.db.query(Task).filter(Task.id == task_id).one()
        task.completion_percent = completion_percent
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
            """
        )
        rows = self.db.execute(sql, {"longitude": longitude, "latitude": latitude, "radius_m": radius_m}).mappings().all()
        ids = [r["id"] for r in rows]
        if not ids:
            return []
        return self.db.query(Task).filter(Task.id.in_(ids)).all()

    # ─── Applications (Choose Mode) ─────────────────────────────────────────

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
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            # Already applied — return existing application
            return (
                self.db.execute(
                    select(TaskApplication).where(
                        TaskApplication.task_id == task_id,
                        TaskApplication.tasker_id == tasker_id,
                    )
                )
                .scalars()
                .one()
            )
        self.db.refresh(application)
        return application

    def list_applications(self, task_id: str) -> list[tuple[TaskApplication, User]]:
        rows = (
            self.db.execute(
                select(TaskApplication, User)
                .join(User, User.id == TaskApplication.tasker_id)
                .where(TaskApplication.task_id == task_id)
                .order_by(TaskApplication.created_at.asc())
            )
            .all()
        )
        return rows

    def accept_task(self, task_id: str, tasker_id: str) -> Task:
        """Fast Mode: tasker self-assigns. Choose Mode: client assigns a specific tasker."""
        task = self.db.query(Task).filter(Task.id == task_id).one()
        task.assigned_to = tasker_id
        task.status = "ASSIGNED"
        # Mark the accepted application, reject the others
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
