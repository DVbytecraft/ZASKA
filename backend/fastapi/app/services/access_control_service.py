from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.access_control import AdminScope, Permission, Role, RolePermission, UserRoleAssignment
from app.models.user import User
from app.services.country_rollout_service import CountryRolloutService


def _uuid() -> str:
    return str(uuid.uuid4())


class AccessControlService:
    DEFAULT_ROLES = {
        "platform_admin": {
            "label": "Admin principal",
            "description": "Accès total à la plateforme, aux modules et aux équipes staff.",
        },
        "finance_admin": {
            "label": "Responsable finance",
            "description": "Vision consolidée finance, exports et comptabilité sociale.",
        },
        "operations_manager": {
            "label": "Manager opérations",
            "description": "Pilotage opérationnel, support et gestion des utilisateurs.",
        },
        "accountant": {
            "label": "Comptable",
            "description": "Accès limité aux chiffres et rapports sur son périmètre.",
        },
        "call_center_agent": {
            "label": "Agent call center",
            "description": "Prise en charge support, tickets et litiges de premier niveau.",
        },
        "kyc_agent": {
            "label": "Agent KYC",
            "description": "Validation et suivi des dossiers d’identité et conformité.",
        },
        "moderator": {
            "label": "Modérateur",
            "description": "Revue des contenus signalés et modération opérationnelle.",
        },
    }

    DEFAULT_PERMISSIONS = {
        "admin.full_access": ("Accès total", "Accès total à l’ensemble des capacités d’administration.", "core"),
        "admin.portal.access": ("Accès portail admin", "Peut ouvrir le back-office Zaska.", "core"),
        "admin.staff.manage": ("Gérer le staff", "Créer les comptes staff et attribuer rôles/scopes.", "core"),
        "admin.roles.manage": ("Gérer les rôles", "Maintenir les rôles et leurs attributions.", "core"),
        "admin.modules.manage": ("Piloter les modules", "Activer ou désactiver les modules par périmètre.", "modules"),
        "admin.countries.manage": ("Piloter les pays", "Gérer les pays et statuts de lancement.", "countries"),
        "admin.food.read": ("Lire le module food", "Voir restaurants, menus et commandes food.", "food"),
        "admin.food.manage": ("Gérer le module food", "Créer et gérer restaurants, menus et commandes food.", "food"),
        "admin.subscriptions.read": ("Lire les abonnements", "Voir les plans et les abonnements clients.", "subscriptions"),
        "admin.subscriptions.manage": ("Gérer les abonnements", "Créer et piloter les plans et abonnements.", "subscriptions"),
        "admin.referrals.read": ("Lire le parrainage", "Voir les programmes, événements et récompenses de parrainage.", "referrals"),
        "admin.referrals.manage": ("Gérer le parrainage", "Mettre à jour les programmes et piloter les récompenses.", "referrals"),
        "admin.finance.read": ("Lire la finance", "Voir les chiffres financiers et la réconciliation.", "finance"),
        "admin.finance.export": ("Exporter la finance", "Télécharger les rapports financiers.", "finance"),
        "admin.social.read": ("Lire les fonds sociaux", "Voir pension, santé et lissage.", "social"),
        "admin.users.read": ("Lire les utilisateurs", "Voir les profils et l’activité utilisateurs.", "users"),
        "admin.users.write": ("Modifier les utilisateurs", "Suspendre, réactiver ou ajuster les comptes.", "users"),
        "admin.kyc.review": ("Revue KYC", "Valider, rejeter et suivre les dossiers KYC.", "kyc"),
        "admin.support.manage": ("Gérer le support", "Gérer les tickets de support et remboursements assistés.", "support"),
        "admin.disputes.manage": ("Gérer les litiges", "Traiter les contestations et escalades.", "disputes"),
        "admin.moderation.review": ("Revue modération", "Traiter les signalements et modérer.", "moderation"),
        "admin.analytics.read": ("Lire les analytics", "Voir les tableaux de bord analytiques.", "analytics"),
    }

    DEFAULT_ROLE_PERMISSION_MAP = {
        "platform_admin": list(DEFAULT_PERMISSIONS.keys()),
        "finance_admin": [
            "admin.portal.access",
            "admin.finance.read",
            "admin.finance.export",
            "admin.social.read",
            "admin.analytics.read",
        ],
        "operations_manager": [
            "admin.portal.access",
            "admin.users.read",
            "admin.users.write",
            "admin.support.manage",
            "admin.disputes.manage",
            "admin.analytics.read",
            "admin.countries.manage",
            "admin.food.read",
            "admin.food.manage",
            "admin.subscriptions.read",
            "admin.subscriptions.manage",
            "admin.referrals.read",
            "admin.referrals.manage",
        ],
        "accountant": [
            "admin.portal.access",
            "admin.finance.read",
            "admin.finance.export",
            "admin.social.read",
            "admin.subscriptions.read",
            "admin.referrals.read",
        ],
        "call_center_agent": [
            "admin.portal.access",
            "admin.support.manage",
            "admin.disputes.manage",
            "admin.users.read",
        ],
        "kyc_agent": [
            "admin.portal.access",
            "admin.kyc.review",
            "admin.users.read",
        ],
        "moderator": [
            "admin.portal.access",
            "admin.moderation.review",
            "admin.users.read",
        ],
    }

    def __init__(self, db: Session):
        self.db = db

    def seed_catalog(self) -> None:
        role_by_code = {
            role.code: role
            for role in self.db.execute(select(Role)).scalars().all()
        }
        permission_by_code = {
            permission.code: permission
            for permission in self.db.execute(select(Permission)).scalars().all()
        }

        changed = False
        for code, config in self.DEFAULT_ROLES.items():
            role = role_by_code.get(code)
            if role is None:
                role = Role(
                    code=code,
                    label=config["label"],
                    description=config["description"],
                    is_system=True,
                    is_staff_role=True,
                )
                self.db.add(role)
                self.db.flush()
                role_by_code[code] = role
                changed = True
            else:
                if role.label != config["label"] or role.description != config["description"]:
                    role.label = config["label"]
                    role.description = config["description"]
                    changed = True

        for code, (label, description, module_key) in self.DEFAULT_PERMISSIONS.items():
            permission = permission_by_code.get(code)
            if permission is None:
                permission = Permission(
                    code=code,
                    label=label,
                    description=description,
                    module_key=module_key,
                )
                self.db.add(permission)
                self.db.flush()
                permission_by_code[code] = permission
                changed = True
            else:
                if (
                    permission.label != label
                    or permission.description != description
                    or permission.module_key != module_key
                ):
                    permission.label = label
                    permission.description = description
                    permission.module_key = module_key
                    changed = True

        existing_pairs = {
            (row.role_id, row.permission_id)
            for row in self.db.execute(select(RolePermission)).scalars().all()
        }
        for role_code, permission_codes in self.DEFAULT_ROLE_PERMISSION_MAP.items():
            role = role_by_code[role_code]
            for permission_code in permission_codes:
                permission = permission_by_code[permission_code]
                pair = (role.id, permission.id)
                if pair in existing_pairs:
                    continue
                self.db.add(RolePermission(role_id=role.id, permission_id=permission.id))
                existing_pairs.add(pair)
                changed = True

        if changed:
            self.db.commit()

    def is_platform_admin(self, user_id: str, user: User | None = None) -> bool:
        user = user or self.db.get(User, user_id)
        if user is None:
            return False
        if user.role == settings.admin_role:
            return True
        return "platform_admin" in self.get_user_role_codes(user_id)

    def user_has_admin_console_access(self, user_id: str, user: User | None = None) -> bool:
        user = user or self.db.get(User, user_id)
        if user is None:
            return False
        if user.role == settings.admin_role:
            return True
        return self.has_permission(user_id, "admin.portal.access", user=user)

    def has_permission(self, user_id: str, permission_code: str, user: User | None = None) -> bool:
        user = user or self.db.get(User, user_id)
        if user is None:
            return False
        if user.role == settings.admin_role:
            return True

        rows = self.db.execute(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(UserRoleAssignment, UserRoleAssignment.role_id == Role.id)
            .where(
                UserRoleAssignment.user_id == user_id,
                UserRoleAssignment.is_active.is_(True),
            )
        ).all()
        codes = {row.code for row in rows}
        return "admin.full_access" in codes or permission_code in codes

    def get_user_role_codes(self, user_id: str) -> list[str]:
        rows = self.db.execute(
            select(Role.code)
            .join(UserRoleAssignment, UserRoleAssignment.role_id == Role.id)
            .where(
                UserRoleAssignment.user_id == user_id,
                UserRoleAssignment.is_active.is_(True),
            )
            .order_by(Role.code.asc())
        ).all()
        return [row.code for row in rows]

    def get_user_scopes(self, user_id: str) -> list[dict]:
        scopes = self.db.execute(
            select(AdminScope)
            .where(AdminScope.user_id == user_id, AdminScope.is_active.is_(True))
            .order_by(AdminScope.scope_type.asc(), AdminScope.scope_value.asc(), AdminScope.module_key.asc())
        ).scalars().all()
        return [
            {
                "scope_type": scope.scope_type,
                "scope_value": scope.scope_value,
                "module_key": scope.module_key,
                "can_read": bool(scope.can_read),
                "can_write": bool(scope.can_write),
            }
            for scope in scopes
        ]

    def list_role_catalog(self) -> list[dict]:
        self.seed_catalog()
        roles = self.db.execute(select(Role).order_by(Role.label.asc())).scalars().all()
        permissions = {
            permission.id: permission
            for permission in self.db.execute(select(Permission)).scalars().all()
        }
        role_permissions = self.db.execute(select(RolePermission)).scalars().all()

        mapping: dict[str, list[Permission]] = {}
        for row in role_permissions:
            mapping.setdefault(row.role_id, []).append(permissions[row.permission_id])

        return [
            {
                "code": role.code,
                "label": role.label,
                "description": role.description,
                "is_system": bool(role.is_system),
                "permissions": [
                    {
                        "code": permission.code,
                        "label": permission.label,
                        "module_key": permission.module_key,
                    }
                    for permission in sorted(mapping.get(role.id, []), key=lambda item: item.code)
                ],
            }
            for role in roles
        ]

    def list_staff_accounts(self) -> list[dict]:
        self.seed_catalog()
        assignments = self.db.execute(
            select(UserRoleAssignment)
            .where(UserRoleAssignment.is_active.is_(True))
            .order_by(UserRoleAssignment.created_at.desc())
        ).scalars().all()
        user_ids = {assignment.user_id for assignment in assignments}
        role_ids = {assignment.role_id for assignment in assignments}
        users = {
            user.id: user
            for user in self.db.execute(select(User).where(User.id.in_(user_ids))).scalars().all()
        } if user_ids else {}
        roles = {
            role.id: role
            for role in self.db.execute(select(Role).where(Role.id.in_(role_ids))).scalars().all()
        } if role_ids else {}

        rows: dict[str, dict] = {}
        for assignment in assignments:
            user = users.get(assignment.user_id)
            role = roles.get(assignment.role_id)
            if user is None or role is None:
                continue
            entry = rows.setdefault(
                user.id,
                {
                    "user_id": user.id,
                    "email": user.email,
                    "phone": user.phone,
                    "full_name": user.full_name,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "country_code": user.country_code,
                    "base_role": user.role,
                    "is_verified": bool(user.is_verified),
                    "is_suspended": bool(user.is_suspended),
                    "is_locked": bool(user.is_locked),
                    "roles": [],
                    "scopes": self.get_user_scopes(user.id),
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                },
            )
            entry["roles"].append(role.code)

        legacy_admins = self.db.execute(
            select(User).where(User.role == settings.admin_role).order_by(User.created_at.desc())
        ).scalars().all()
        for user in legacy_admins:
            rows.setdefault(
                user.id,
                {
                    "user_id": user.id,
                    "email": user.email,
                    "phone": user.phone,
                    "full_name": user.full_name,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "country_code": user.country_code,
                    "base_role": user.role,
                    "is_verified": bool(user.is_verified),
                    "is_suspended": bool(user.is_suspended),
                    "is_locked": bool(user.is_locked),
                    "roles": ["platform_admin"],
                    "scopes": self.get_user_scopes(user.id),
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                },
            )

        return list(rows.values())

    def create_staff_account(
        self,
        *,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        created_by_user_id: str,
        role_codes: list[str],
        scopes: list[dict] | None = None,
        country_code: str | None = None,
        phone: str | None = None,
    ) -> User:
        self.seed_catalog()
        email_norm = email.strip().lower()
        phone_norm = phone.strip() if phone else None
        country_norm = country_code.strip().upper() if country_code else None

        if self.db.execute(select(User).where(User.email == email_norm)).scalars().one_or_none():
            raise ValueError("Un compte existe déjà avec cet email.")
        if phone_norm and self.db.execute(select(User).where(User.phone == phone_norm)).scalars().one_or_none():
            raise ValueError("Un compte existe déjà avec ce numéro de téléphone.")

        default_scopes = scopes or [
            {
                "scope_type": "global",
                "scope_value": "*",
                "module_key": "*",
                "can_read": True,
                "can_write": "platform_admin" in role_codes,
            }
        ]
        user = User(
            id=_uuid(),
            email=email_norm,
            phone=phone_norm,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            full_name=f"{first_name.strip()} {last_name.strip()}".strip(),
            password_hash=get_password_hash(password),
            role="staff",
            is_verified=True,
            country_code=country_norm,
        )
        self.db.add(user)
        self.db.flush()

        self.replace_role_assignments(
            user_id=user.id,
            role_codes=role_codes,
            granted_by_user_id=created_by_user_id,
            commit=False,
        )
        self.replace_scopes(
            user_id=user.id,
            scopes=default_scopes,
            granted_by_user_id=created_by_user_id,
            commit=False,
        )

        self.db.commit()
        self.db.refresh(user)

        if country_norm:
            CountryRolloutService(self.db).ensure_country(country_norm)

        if user.email:
            try:
                from app.core.email import send_welcome_email

                if send_welcome_email(user.email, user.full_name or user.first_name or "Bienvenue"):
                    user.welcome_email_sent_at = datetime.now(timezone.utc)
                    self.db.commit()
            except Exception:
                self.db.rollback()

        return user

    def replace_role_assignments(
        self,
        *,
        user_id: str,
        role_codes: list[str],
        granted_by_user_id: str,
        commit: bool = True,
    ) -> list[str]:
        self.seed_catalog()
        normalized = sorted({code.strip() for code in role_codes if code and code.strip()})
        if not normalized:
            raise ValueError("Au moins un rôle staff est requis.")

        roles = self.db.execute(select(Role).where(Role.code.in_(normalized))).scalars().all()
        role_by_code = {role.code: role for role in roles}
        missing = [code for code in normalized if code not in role_by_code]
        if missing:
            raise ValueError(f"Rôles inconnus: {', '.join(missing)}")

        existing = self.db.execute(
            select(UserRoleAssignment).where(UserRoleAssignment.user_id == user_id)
        ).scalars().all()
        existing_by_role_id = {row.role_id: row for row in existing}
        target_role_ids = {role_by_code[code].id for code in normalized}
        now = datetime.now(timezone.utc)

        for role in roles:
            row = existing_by_role_id.get(role.id)
            if row is None:
                self.db.add(
                    UserRoleAssignment(
                        user_id=user_id,
                        role_id=role.id,
                        assigned_by_user_id=granted_by_user_id,
                        is_active=True,
                    )
                )
                continue
            row.is_active = True
            row.assigned_by_user_id = granted_by_user_id
            row.updated_at = now
            row.revoked_at = None

        for row in existing:
            if row.role_id in target_role_ids:
                continue
            row.is_active = False
            row.updated_at = now
            row.revoked_at = now

        if commit:
            self.db.commit()
        return normalized

    def replace_scopes(
        self,
        *,
        user_id: str,
        scopes: list[dict],
        granted_by_user_id: str,
        commit: bool = True,
    ) -> list[dict]:
        normalized = [
            {
                "scope_type": str(scope.get("scope_type", "")).strip().lower(),
                "scope_value": str(scope.get("scope_value", "*")).strip().upper() or "*",
                "module_key": str(scope.get("module_key", "*")).strip().lower() or "*",
                "can_read": bool(scope.get("can_read", True)),
                "can_write": bool(scope.get("can_write", False)),
            }
            for scope in scopes
            if str(scope.get("scope_type", "")).strip()
        ]
        if not normalized:
            raise ValueError("Au moins un scope valide est requis.")

        existing = self.db.execute(
            select(AdminScope).where(AdminScope.user_id == user_id)
        ).scalars().all()
        existing_by_key = {
            (row.scope_type, row.scope_value, row.module_key): row
            for row in existing
        }
        target_keys = {
            (scope["scope_type"], scope["scope_value"], scope["module_key"])
            for scope in normalized
        }
        now = datetime.now(timezone.utc)

        for scope in normalized:
            key = (scope["scope_type"], scope["scope_value"], scope["module_key"])
            row = existing_by_key.get(key)
            if row is None:
                self.db.add(
                    AdminScope(
                        user_id=user_id,
                        scope_type=scope["scope_type"],
                        scope_value=scope["scope_value"],
                        module_key=scope["module_key"],
                        can_read=scope["can_read"],
                        can_write=scope["can_write"],
                        is_active=True,
                        created_by_user_id=granted_by_user_id,
                    )
                )
                continue
            row.can_read = scope["can_read"]
            row.can_write = scope["can_write"]
            row.is_active = True
            row.created_by_user_id = granted_by_user_id
            row.updated_at = now

        for row in existing:
            key = (row.scope_type, row.scope_value, row.module_key)
            if key in target_keys:
                continue
            row.is_active = False
            row.updated_at = now

        if commit:
            self.db.commit()
        return normalized
