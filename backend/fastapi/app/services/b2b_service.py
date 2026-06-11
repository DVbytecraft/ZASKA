from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.b2b import (
    AdminExportJob,
    BusinessContract,
    BusinessMembership,
    BusinessOrganization,
    BusinessTaskTemplate,
    BusinessWorkOrder,
)
from app.models.dispute import DisputeRecord
from app.models.task import Task
from app.models.user import User
from app.models.wallet import Wallet
from app.services.country_rollout_service import CountryRolloutService


class B2BService:
    def __init__(self, db: Session):
        self.db = db

    def create_business_user(
        self,
        *,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        country_code: str | None = None,
        phone: str | None = None,
        created_by_user_id: str | None = None,
    ) -> dict:
        email_norm = email.strip().lower()
        existing = self.db.execute(select(User).where(User.email == email_norm)).scalars().one_or_none()
        if existing is not None:
            raise ValueError("Email déjà utilisé")

        user = User(
            id=str(uuid.uuid4()),
            email=email_norm,
            phone=phone.strip() if phone else None,
            first_name=first_name,
            last_name=last_name,
            full_name=f"{first_name} {last_name}".strip(),
            password_hash=get_password_hash(password),
            role="business",
            is_verified=True,
            country_code=country_code.upper() if country_code else None,
        )
        self.db.add(user)
        self.db.flush()
        self._ensure_wallets(user.id, user.country_code)
        self.db.commit()
        self.db.refresh(user)
        if user.country_code:
            CountryRolloutService(self.db).ensure_country(user.country_code)
        return {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "firstName": user.first_name,
            "lastName": user.last_name,
            "countryCode": user.country_code,
            "createdByUserId": created_by_user_id,
        }

    def create_organization(
        self,
        *,
        name: str,
        legal_name: str | None,
        registration_number: str | None,
        country_code: str | None,
        continent_code: str | None,
        billing_mode: str,
        created_by_user_id: str,
        metadata: dict | None = None,
    ) -> dict:
        organization = BusinessOrganization(
            name=name,
            legal_name=legal_name,
            registration_number=registration_number,
            country_code=country_code.upper() if country_code else None,
            continent_code=continent_code.upper() if continent_code else None,
            billing_mode=billing_mode,
            created_by_user_id=created_by_user_id,
            metadata_json=json.dumps(metadata) if metadata is not None else None,
        )
        self.db.add(organization)
        self.db.commit()
        self.db.refresh(organization)
        return self._serialize_org(organization)

    def list_organizations(
        self,
        *,
        country_code: str | None = None,
        continent_code: str | None = None,
        status: str | None = None,
    ) -> list[dict]:
        stmt = select(BusinessOrganization).order_by(desc(BusinessOrganization.created_at))
        if country_code:
            stmt = stmt.where(BusinessOrganization.country_code == country_code.upper())
        if continent_code:
            stmt = stmt.where(BusinessOrganization.continent_code == continent_code.upper())
        if status:
            stmt = stmt.where(BusinessOrganization.status == status)
        rows = self.db.execute(stmt).scalars().all()
        return [self._serialize_org(row) for row in rows]

    def add_membership(
        self,
        *,
        organization_id: str,
        user_id: str,
        member_role: str,
        is_primary: bool = False,
    ) -> dict:
        organization = self.db.get(BusinessOrganization, organization_id)
        if organization is None:
            raise ValueError("Organisation introuvable")
        user = self.db.get(User, user_id)
        if user is None:
            raise ValueError("Utilisateur introuvable")

        existing = self.db.execute(
            select(BusinessMembership).where(
                BusinessMembership.organization_id == organization_id,
                BusinessMembership.user_id == user_id,
            )
        ).scalars().one_or_none()
        if existing is not None:
            raise ValueError("Cet utilisateur est déjà membre de l'organisation")

        membership = BusinessMembership(
            organization_id=organization_id,
            user_id=user_id,
            member_role=member_role,
            is_primary=is_primary,
        )
        self.db.add(membership)
        self.db.commit()
        self.db.refresh(membership)
        return self._serialize_membership(membership)

    def create_contract(
        self,
        *,
        organization_id: str,
        plan_name: str,
        monthly_task_quota: int | None,
        overage_price: Decimal | None,
        currency: str,
        status: str,
        start_date: datetime | None,
        end_date: datetime | None,
        terms: dict | None = None,
    ) -> dict:
        if self.db.get(BusinessOrganization, organization_id) is None:
            raise ValueError("Organisation introuvable")
        contract = BusinessContract(
            organization_id=organization_id,
            plan_name=plan_name,
            monthly_task_quota=monthly_task_quota,
            overage_price=overage_price,
            currency=currency.upper(),
            status=status,
            start_date=start_date,
            end_date=end_date,
            terms_json=json.dumps(terms) if terms is not None else None,
        )
        self.db.add(contract)
        self.db.commit()
        self.db.refresh(contract)
        return self._serialize_contract(contract)

    def create_template(
        self,
        *,
        organization_id: str,
        title: str,
        description: str,
        service_category: str,
        default_price: Decimal,
        currency: str,
        city: str | None,
        country_code: str | None,
        is_active: bool = True,
        template: dict | None = None,
    ) -> dict:
        if self.db.get(BusinessOrganization, organization_id) is None:
            raise ValueError("Organisation introuvable")
        item = BusinessTaskTemplate(
            organization_id=organization_id,
            title=title,
            description=description,
            service_category=service_category,
            default_price=default_price,
            currency=currency.upper(),
            city=city,
            country_code=country_code.upper() if country_code else None,
            is_active=is_active,
            template_json=json.dumps(template) if template is not None else None,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return self._serialize_template(item)

    def list_templates(self, organization_id: str | None = None) -> list[dict]:
        stmt = select(BusinessTaskTemplate).order_by(desc(BusinessTaskTemplate.created_at))
        if organization_id:
            stmt = stmt.where(BusinessTaskTemplate.organization_id == organization_id)
        rows = self.db.execute(stmt).scalars().all()
        return [self._serialize_template(row) for row in rows]

    def create_work_order(
        self,
        *,
        organization_id: str,
        requested_by_user_id: str,
        template_id: str | None,
        beneficiary_name: str | None,
        beneficiary_phone: str | None,
        scheduled_at: datetime | None,
        price: Decimal,
        currency: str,
        notes: str | None = None,
        assigned_tasker_id: str | None = None,
        linked_task_id: str | None = None,
        status: str = "draft",
    ) -> dict:
        if self.db.get(BusinessOrganization, organization_id) is None:
            raise ValueError("Organisation introuvable")
        if self.db.get(User, requested_by_user_id) is None:
            raise ValueError("Demandeur introuvable")
        order = BusinessWorkOrder(
            organization_id=organization_id,
            template_id=template_id,
            requested_by_user_id=requested_by_user_id,
            assigned_tasker_id=assigned_tasker_id,
            linked_task_id=linked_task_id,
            beneficiary_name=beneficiary_name,
            beneficiary_phone=beneficiary_phone,
            status=status,
            scheduled_at=scheduled_at,
            price=price,
            currency=currency.upper(),
            notes=notes,
        )
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)
        return self._serialize_work_order(order)

    def list_work_orders(
        self,
        *,
        organization_id: str | None = None,
        status: str | None = None,
        requested_by_user_id: str | None = None,
    ) -> list[dict]:
        stmt = select(BusinessWorkOrder).order_by(desc(BusinessWorkOrder.created_at))
        if organization_id:
            stmt = stmt.where(BusinessWorkOrder.organization_id == organization_id)
        if status:
            stmt = stmt.where(BusinessWorkOrder.status == status)
        if requested_by_user_id:
            stmt = stmt.where(BusinessWorkOrder.requested_by_user_id == requested_by_user_id)
        rows = self.db.execute(stmt).scalars().all()
        return [self._serialize_work_order(row) for row in rows]

    def get_my_dashboard(self, user_id: str) -> dict:
        memberships = self.db.execute(
            select(BusinessMembership).where(
                BusinessMembership.user_id == user_id,
                BusinessMembership.status == "active",
            )
        ).scalars().all()
        organization_ids = [item.organization_id for item in memberships]
        organizations = []
        contracts = []
        templates = []
        orders = []
        for org_id in organization_ids:
            org = self.db.get(BusinessOrganization, org_id)
            if org:
                organizations.append(self._serialize_org(org))
            contracts.extend(self.list_contracts(org_id))
            templates.extend(self.list_templates(org_id))
            orders.extend(self.list_work_orders(organization_id=org_id))
        return {
            "memberships": [self._serialize_membership(item) for item in memberships],
            "organizations": organizations,
            "contracts": contracts,
            "templates": templates,
            "workOrders": orders,
        }

    def list_contracts(self, organization_id: str | None = None) -> list[dict]:
        stmt = select(BusinessContract).order_by(desc(BusinessContract.created_at))
        if organization_id:
            stmt = stmt.where(BusinessContract.organization_id == organization_id)
        rows = self.db.execute(stmt).scalars().all()
        return [self._serialize_contract(row) for row in rows]

    def generate_export(
        self,
        *,
        requested_by_user_id: str,
        report_type: str,
        export_format: str,
        country_code: str | None = None,
        continent_code: str | None = None,
        filters: dict | None = None,
    ) -> dict:
        data = self._build_report(
            report_type=report_type,
            country_code=country_code,
            continent_code=continent_code,
            filters=filters or {},
        )
        job = AdminExportJob(
            report_type=report_type,
            export_format=export_format,
            status="completed",
            requested_by_user_id=requested_by_user_id,
            country_code=country_code.upper() if country_code else None,
            continent_code=continent_code.upper() if continent_code else None,
            filters_json=json.dumps(filters or {}),
            result_json=json.dumps(data),
            completed_at=datetime.now(timezone.utc),
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return self._serialize_export_job(job)

    def list_export_jobs(self, report_type: str | None = None, requested_by_user_id: str | None = None) -> list[dict]:
        stmt = select(AdminExportJob).order_by(desc(AdminExportJob.created_at))
        if report_type:
            stmt = stmt.where(AdminExportJob.report_type == report_type)
        if requested_by_user_id:
            stmt = stmt.where(AdminExportJob.requested_by_user_id == requested_by_user_id)
        rows = self.db.execute(stmt).scalars().all()
        return [self._serialize_export_job(row) for row in rows]

    def get_export_job(self, export_job_id: str) -> dict:
        job = self.db.get(AdminExportJob, export_job_id)
        if job is None:
            raise ValueError("Export introuvable")
        return self._serialize_export_job(job)

    def _build_report(
        self,
        *,
        report_type: str,
        country_code: str | None,
        continent_code: str | None,
        filters: dict,
    ) -> dict:
        if report_type == "taskers_active":
            query = select(User).where(User.role == "tasker")
            if country_code:
                query = query.where(User.country_code == country_code.upper())
            users = self.db.execute(query).scalars().all()
            rows = []
            for user in users:
                tasks_count = self.db.execute(
                    select(func.count(Task.id)).where(
                        Task.assigned_to == user.id,
                        Task.status.in_(["ASSIGNED", "PENDING_VALIDATION", "COMPLETED"]),
                    )
                ).scalar_one()
                rows.append(
                    {
                        "userId": user.id,
                        "fullName": user.full_name,
                        "countryCode": user.country_code,
                        "ratingCount": user.rating_count,
                        "tasksCount": int(tasks_count or 0),
                    }
                )
            return {"columns": list(rows[0].keys()) if rows else [], "rows": rows}

        if report_type == "disputes_monthly":
            rows = []
            disputes = self.db.execute(select(DisputeRecord).order_by(desc(DisputeRecord.created_at))).scalars().all()
            for item in disputes:
                rows.append(
                    {
                        "disputeId": item.id,
                        "status": item.status,
                        "type": item.dispute_type,
                        "userId": item.user_id,
                        "createdAt": item.created_at.isoformat() if item.created_at else None,
                    }
                )
            return {"columns": list(rows[0].keys()) if rows else [], "rows": rows}

        if report_type == "b2b_organizations":
            rows = self.list_organizations(country_code=country_code, continent_code=continent_code)
            return {"columns": list(rows[0].keys()) if rows else [], "rows": rows}

        if report_type == "financial_monthly":
            tasks_query = select(Task)
            if country_code:
                tasks_query = tasks_query.where(Task.country == country_code.upper())
            tasks = self.db.execute(tasks_query).scalars().all()
            total_gross = sum(Decimal(str(task.price)) for task in tasks)
            rows = [
                {
                    "tasksCount": len(tasks),
                    "grossVolume": str(total_gross),
                    "currency": filters.get("currency", "mixed"),
                }
            ]
            return {"columns": list(rows[0].keys()), "rows": rows}

        if report_type == "pension_taskers":
            users = self.db.execute(select(User).where(User.role == "tasker")).scalars().all()
            rows = [
                {
                    "userId": user.id,
                    "fullName": user.full_name,
                    "countryCode": user.country_code,
                    "taskerSecurityVerified": bool(user.tasker_security_verified),
                }
                for user in users
            ]
            return {"columns": list(rows[0].keys()) if rows else [], "rows": rows}

        raise ValueError("Type d'export non supporté")

    def _ensure_wallets(self, user_id: str, country_code: str | None) -> None:
        currencies = {"USD"}
        if country_code:
            currencies.add(CountryRolloutService(self.db).resolve_local_currency(country_code, fallback="EUR"))
        for currency in currencies:
            self.db.add(Wallet(user_id=user_id, currency=currency, balance=Decimal("0")))

    def _serialize_org(self, row: BusinessOrganization) -> dict:
        return {
            "id": row.id,
            "name": row.name,
            "legalName": row.legal_name,
            "registrationNumber": row.registration_number,
            "countryCode": row.country_code,
            "continentCode": row.continent_code,
            "billingMode": row.billing_mode,
            "status": row.status,
            "createdByUserId": row.created_by_user_id,
            "metadata": json.loads(row.metadata_json) if row.metadata_json else None,
            "createdAt": row.created_at.isoformat() if row.created_at else None,
        }

    def _serialize_membership(self, row: BusinessMembership) -> dict:
        return {
            "id": row.id,
            "organizationId": row.organization_id,
            "userId": row.user_id,
            "memberRole": row.member_role,
            "status": row.status,
            "isPrimary": bool(row.is_primary),
            "createdAt": row.created_at.isoformat() if row.created_at else None,
        }

    def _serialize_contract(self, row: BusinessContract) -> dict:
        return {
            "id": row.id,
            "organizationId": row.organization_id,
            "planName": row.plan_name,
            "monthlyTaskQuota": row.monthly_task_quota,
            "overagePrice": str(row.overage_price) if row.overage_price is not None else None,
            "currency": row.currency,
            "status": row.status,
            "startDate": row.start_date.isoformat() if row.start_date else None,
            "endDate": row.end_date.isoformat() if row.end_date else None,
            "terms": json.loads(row.terms_json) if row.terms_json else None,
            "createdAt": row.created_at.isoformat() if row.created_at else None,
        }

    def _serialize_template(self, row: BusinessTaskTemplate) -> dict:
        return {
            "id": row.id,
            "organizationId": row.organization_id,
            "title": row.title,
            "description": row.description,
            "serviceCategory": row.service_category,
            "defaultPrice": str(row.default_price),
            "currency": row.currency,
            "city": row.city,
            "countryCode": row.country_code,
            "isActive": bool(row.is_active),
            "template": json.loads(row.template_json) if row.template_json else None,
            "createdAt": row.created_at.isoformat() if row.created_at else None,
        }

    def _serialize_work_order(self, row: BusinessWorkOrder) -> dict:
        return {
            "id": row.id,
            "organizationId": row.organization_id,
            "templateId": row.template_id,
            "requestedByUserId": row.requested_by_user_id,
            "assignedTaskerId": row.assigned_tasker_id,
            "linkedTaskId": row.linked_task_id,
            "beneficiaryName": row.beneficiary_name,
            "beneficiaryPhone": row.beneficiary_phone,
            "status": row.status,
            "source": row.source,
            "scheduledAt": row.scheduled_at.isoformat() if row.scheduled_at else None,
            "price": str(row.price),
            "currency": row.currency,
            "notes": row.notes,
            "createdAt": row.created_at.isoformat() if row.created_at else None,
        }

    def _serialize_export_job(self, row: AdminExportJob) -> dict:
        return {
            "id": row.id,
            "reportType": row.report_type,
            "exportFormat": row.export_format,
            "status": row.status,
            "requestedByUserId": row.requested_by_user_id,
            "countryCode": row.country_code,
            "continentCode": row.continent_code,
            "filters": json.loads(row.filters_json) if row.filters_json else None,
            "result": json.loads(row.result_json) if row.result_json else None,
            "completedAt": row.completed_at.isoformat() if row.completed_at else None,
            "createdAt": row.created_at.isoformat() if row.created_at else None,
        }
