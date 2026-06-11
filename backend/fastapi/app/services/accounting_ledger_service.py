from __future__ import annotations

import json
import uuid
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.observability import logger
from app.models.accounting import (
    CountryRevenueSnapshot,
    FinancialAccount,
    FinancialAccountScope,
    LedgerEntry,
    ReconciliationSnapshot,
)
from app.models.food import RestaurantPayoutSnapshot, RestaurantPartner
from app.models.location_config import Country
from app.models.task import Task
from app.models.user import User
from app.models.wallet import Transaction, Wallet
from app.services.wallet_service import (
    LEGACY_SPLIT_MODEL,
    SOCIAL_SPLIT_LINES,
    SOCIAL_SPLIT_MODEL,
    WalletService,
)


def _uuid() -> str:
    return str(uuid.uuid4())


_ZERO = Decimal("0")
_DRIFT_TOLERANCE = Decimal("0.000001")


class AccountingLedgerService:
    DEFAULT_ACCOUNT_DEFINITIONS = {
        "TASKER_NET_DISTRIBUTION": {
            "label": "Paiements nets Taskers",
            "account_type": "distribution",
            "module_code": "TASKS",
            "owner_setting": None,
        },
        "ZASKA_OPERATIONS": {
            "label": "Compte exploitation Zaska",
            "account_type": "fund",
            "module_code": "ACCOUNTING",
            "owner_setting": "zaska_wallet_user_id",
        },
        "PENSION_FUND": {
            "label": "Fonds pension Zaska",
            "account_type": "fund",
            "module_code": "SOCIAL_PROTECTION",
            "owner_setting": "pension_fund_user_id",
        },
        "HEALTH_FUND": {
            "label": "Fonds santé Zaska",
            "account_type": "fund",
            "module_code": "SOCIAL_PROTECTION",
            "owner_setting": "health_fund_user_id",
        },
        "SMOOTHING_FUND": {
            "label": "Fonds de lissage Zaska",
            "account_type": "fund",
            "module_code": "SOCIAL_PROTECTION",
            "owner_setting": "smoothing_fund_user_id",
        },
        "ESCROW_CLEARING": {
            "label": "Compte de compensation escrow",
            "account_type": "clearing",
            "module_code": "TASKS",
            "owner_setting": None,
        },
        "WITHDRAWAL_FEES_REVENUE": {
            "label": "Revenus frais de retrait",
            "account_type": "revenue",
            "module_code": "ACCOUNTING",
            "owner_setting": None,
        },
        "FX_MARGIN_REVENUE": {
            "label": "Revenus marge de change",
            "account_type": "revenue",
            "module_code": "DIASPORA",
            "owner_setting": None,
        },
        "VAT_PAYABLE": {
            "label": "TVA à reverser",
            "account_type": "liability",
            "module_code": "ACCOUNTING",
            "owner_setting": None,
        },
        "RESTAURANT_PAYOUTS_RELEASED": {
            "label": "Payouts restaurants libérés",
            "account_type": "expense",
            "module_code": "FOOD",
            "owner_setting": None,
        },
        "RESTAURANT_PAYOUTS_PENDING": {
            "label": "Payouts restaurants en attente",
            "account_type": "liability",
            "module_code": "FOOD",
            "owner_setting": None,
        },
        "RESTAURANT_PAYOUTS_REFUNDED": {
            "label": "Payouts restaurants remboursés",
            "account_type": "contra_expense",
            "module_code": "FOOD",
            "owner_setting": None,
        },
    }

    SYSTEM_ACCOUNT_CODE_BY_SETTING = {
        "zaska_wallet_user_id": "ZASKA_OPERATIONS",
        "pension_fund_user_id": "PENSION_FUND",
        "health_fund_user_id": "HEALTH_FUND",
        "smoothing_fund_user_id": "SMOOTHING_FUND",
    }

    TASKER_SPLIT_ACCOUNT_CODE = "TASKER_NET_DISTRIBUTION"

    def __init__(self, db: Session) -> None:
        self.db = db
        self.wallet_service = WalletService(db)

    def seed_chart_of_accounts(self) -> list[dict[str, object]]:
        currencies = self._known_currencies()
        changed = False
        for currency in currencies:
            for code, config in self.DEFAULT_ACCOUNT_DEFINITIONS.items():
                owner_user_id = self._resolve_owner_user_id(config.get("owner_setting"))
                account = self._find_account(code=code, currency=currency)
                if account is None:
                    account = FinancialAccount(
                        id=_uuid(),
                        code=code,
                        label=str(config["label"]),
                        account_type=str(config["account_type"]),
                        scope_type="global",
                        scope_value="*",
                        module_code=str(config["module_code"]),
                        currency=currency,
                        owner_user_id=owner_user_id,
                        is_system=True,
                        is_active=True,
                        metadata_json=json.dumps({"seeded": True}),
                    )
                    self.db.add(account)
                    self.db.flush()
                    changed = True
                else:
                    if (
                        account.label != str(config["label"])
                        or account.account_type != str(config["account_type"])
                        or account.module_code != str(config["module_code"])
                        or account.owner_user_id != owner_user_id
                        or not account.is_system
                    ):
                        account.label = str(config["label"])
                        account.account_type = str(config["account_type"])
                        account.module_code = str(config["module_code"])
                        account.owner_user_id = owner_user_id
                        account.is_system = True
                        account.is_active = True
                        changed = True
                changed = self._ensure_global_scope(account) or changed

        if changed:
            self.db.commit()
        return self.list_accounts()

    def list_accounts(
        self,
        *,
        currency: str | None = None,
        code: str | None = None,
        account_type: str | None = None,
    ) -> list[dict[str, object]]:
        stmt = select(FinancialAccount).where(FinancialAccount.is_active.is_(True))
        if currency:
            stmt = stmt.where(FinancialAccount.currency == currency.upper())
        if code:
            stmt = stmt.where(FinancialAccount.code == code.upper())
        if account_type:
            stmt = stmt.where(FinancialAccount.account_type == account_type)
        accounts = self.db.execute(
            stmt.order_by(FinancialAccount.code.asc(), FinancialAccount.currency.asc())
        ).scalars().all()
        balances = self._ledger_balances_map([account.id for account in accounts])
        return [self._serialize_account(account, balances.get(account.id, _ZERO)) for account in accounts]

    def ingest_wallet_mirror_entries(self) -> dict[str, object]:
        self.seed_chart_of_accounts()
        created = 0
        scanned = 0
        mirrored_system = 0
        mirrored_tasker_net = 0

        system_owner_map = self._system_owner_to_account_code()
        if system_owner_map:
            system_rows = self.db.execute(
                select(Transaction, Wallet)
                .join(Wallet, Wallet.id == Transaction.wallet_id)
                .where(
                    Transaction.status == "completed",
                    Wallet.user_id.in_(list(system_owner_map.keys())),
                )
                .order_by(Transaction.created_at.asc())
            ).all()
            task_context = self._build_task_context([
                self.wallet_service._parse_metadata(tx).get("task_id")
                for tx, _wallet in system_rows
            ])
            for tx, wallet in system_rows:
                scanned += 1
                account_code = system_owner_map.get(wallet.user_id)
                if not account_code:
                    continue
                account = self._get_or_create_account(account_code, wallet.currency)
                metadata = self.wallet_service._parse_metadata(tx)
                task_id = str(metadata.get("task_id") or "") or None
                country_code = self._resolve_country_code(task_id=task_id, task_context=task_context, metadata=metadata)
                if self._insert_ledger_entry(
                    account=account,
                    direction=tx.type,
                    amount=Decimal(str(tx.amount)),
                    currency=wallet.currency,
                    reference=tx.reference,
                    source_table="transactions",
                    source_id=tx.id,
                    country_code=country_code,
                    module_code=self._account_module_code(account.code),
                    entry_type="wallet_mirror",
                    journal_id=self._journal_id_for_transaction(tx.reference, metadata),
                    metadata={
                        "wallet_id": wallet.id,
                        "wallet_user_id": wallet.user_id,
                        "transaction_metadata": metadata,
                    },
                    created_at=tx.created_at,
                ):
                    created += 1
                    mirrored_system += 1

        tasker_rows = self.db.execute(
            select(Transaction, Wallet)
            .join(Wallet, Wallet.id == Transaction.wallet_id)
            .where(
                Transaction.status == "completed",
                Transaction.type == "credit",
                Transaction.reference.like("escrow_release:%"),
            )
            .order_by(Transaction.created_at.asc())
        ).all()
        task_context = self._build_task_context([
            self.wallet_service._parse_metadata(tx).get("task_id")
            for tx, _wallet in tasker_rows
        ])
        for tx, wallet in tasker_rows:
            metadata = self.wallet_service._parse_metadata(tx)
            if metadata.get("split_line") != "tasker_net":
                continue
            scanned += 1
            account = self._get_or_create_account(self.TASKER_SPLIT_ACCOUNT_CODE, wallet.currency)
            task_id = str(metadata.get("task_id") or "") or None
            country_code = self._resolve_country_code(task_id=task_id, task_context=task_context, metadata=metadata)
            if self._insert_ledger_entry(
                account=account,
                direction="credit",
                amount=Decimal(str(tx.amount)),
                currency=wallet.currency,
                reference=tx.reference,
                source_table="transactions",
                source_id=tx.id,
                country_code=country_code,
                module_code="TASKS",
                entry_type="tasker_distribution",
                journal_id=self._journal_id_for_transaction(tx.reference, metadata),
                metadata={
                    "wallet_id": wallet.id,
                    "wallet_user_id": wallet.user_id,
                    "transaction_metadata": metadata,
                },
                created_at=tx.created_at,
            ):
                created += 1
                mirrored_tasker_net += 1

        self.db.commit()
        return {
            "scanned_transactions": scanned,
            "created_entries": created,
            "mirrored_system_entries": mirrored_system,
            "mirrored_tasker_net_entries": mirrored_tasker_net,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def record_transaction_realtime(self, tx: Transaction, wallet: Wallet) -> int:
        """
        Mirror a single completed wallet Transaction into the ledger immediately,
        within the caller's own DB transaction (no commit here).

        This is the real-time counterpart of ingest_wallet_mirror_entries(): it
        covers the same two cases (system/fund-owned wallet movements, and
        tasker_net escrow-release credits) for exactly one transaction, so the
        ledger never needs a manual ingest run to stay in sync. Idempotent via
        _insert_ledger_entry's reference+account+direction uniqueness check.

        Returns the number of LedgerEntry rows created (0, 1 or 2).
        """
        if tx.status != "completed":
            return 0

        # Sandbox transactions never touch real money — keep them out of the
        # accounting ledger entirely so reconciliation/reporting stays accurate.
        if tx.is_sandbox:
            return 0

        metadata = self.wallet_service._parse_metadata(tx)
        task_id = str(metadata.get("task_id") or "") or None
        task_context = self._build_task_context([task_id]) if task_id else {}
        country_code = self._resolve_country_code(task_id=task_id, task_context=task_context, metadata=metadata)
        journal_id = self._journal_id_for_transaction(tx.reference, metadata)
        entry_metadata = {
            "wallet_id": wallet.id,
            "wallet_user_id": wallet.user_id,
            "transaction_metadata": metadata,
        }

        created = 0

        account_code = self._system_owner_to_account_code().get(wallet.user_id)
        if account_code:
            account = self._get_or_create_account(account_code, wallet.currency)
            if self._insert_ledger_entry(
                account=account,
                direction=tx.type,
                amount=Decimal(str(tx.amount)),
                currency=wallet.currency,
                reference=tx.reference,
                source_table="transactions",
                source_id=tx.id,
                country_code=country_code,
                module_code=self._account_module_code(account.code),
                entry_type="wallet_mirror",
                journal_id=journal_id,
                metadata=entry_metadata,
                created_at=tx.created_at,
            ):
                created += 1

        if (
            tx.type == "credit"
            and tx.reference.startswith("escrow_release:")
            and metadata.get("split_line") == "tasker_net"
        ):
            account = self._get_or_create_account(self.TASKER_SPLIT_ACCOUNT_CODE, wallet.currency)
            if self._insert_ledger_entry(
                account=account,
                direction="credit",
                amount=Decimal(str(tx.amount)),
                currency=wallet.currency,
                reference=tx.reference,
                source_table="transactions",
                source_id=tx.id,
                country_code=country_code,
                module_code="TASKS",
                entry_type="tasker_distribution",
                journal_id=journal_id,
                metadata=entry_metadata,
                created_at=tx.created_at,
            ):
                created += 1

        return created

    def create_reconciliation_snapshots(
        self,
        *,
        snapshot_date: date | None = None,
        currency: str | None = None,
    ) -> list[dict[str, object]]:
        self.seed_chart_of_accounts()
        target_date = snapshot_date or datetime.now(timezone.utc).date()
        stmt = select(FinancialAccount).where(
            FinancialAccount.is_active.is_(True),
            FinancialAccount.owner_user_id.is_not(None),
        )
        if currency:
            stmt = stmt.where(FinancialAccount.currency == currency.upper())
        accounts = self.db.execute(
            stmt.order_by(FinancialAccount.code.asc(), FinancialAccount.currency.asc())
        ).scalars().all()

        results: list[dict[str, object]] = []
        for account in accounts:
            account_currency = account.currency or currency or "XOF"
            ledger_balance = self._ledger_balance_for_account(account.id)
            source_wallet_balance = self._source_wallet_balance(account.owner_user_id, account_currency)
            drift_amount = source_wallet_balance - ledger_balance
            status = "ok" if abs(drift_amount) <= _DRIFT_TOLERANCE else "drift"
            row = self.db.execute(
                select(ReconciliationSnapshot).where(
                    ReconciliationSnapshot.snapshot_date == target_date,
                    ReconciliationSnapshot.account_id == account.id,
                    ReconciliationSnapshot.currency == account_currency,
                )
            ).scalars().one_or_none()
            payload = {
                "account_code": account.code,
                "owner_user_id": account.owner_user_id,
            }
            if row is None:
                row = ReconciliationSnapshot(
                    id=_uuid(),
                    account_id=account.id,
                    snapshot_date=target_date,
                    currency=account_currency,
                    ledger_balance=ledger_balance,
                    source_wallet_balance=source_wallet_balance,
                    drift_amount=drift_amount,
                    status=status,
                    metadata_json=json.dumps(payload),
                )
                self.db.add(row)
            else:
                row.ledger_balance = ledger_balance
                row.source_wallet_balance = source_wallet_balance
                row.drift_amount = drift_amount
                row.status = status
                row.metadata_json = json.dumps(payload)

            results.append(self._serialize_reconciliation_snapshot(row, account))

        self.db.commit()
        return results

    def list_reconciliation_snapshots(
        self,
        *,
        snapshot_date: date | None = None,
        currency: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, object]]:
        stmt = (
            select(ReconciliationSnapshot, FinancialAccount)
            .join(FinancialAccount, FinancialAccount.id == ReconciliationSnapshot.account_id)
            .order_by(ReconciliationSnapshot.snapshot_date.desc(), FinancialAccount.code.asc())
            .limit(limit)
        )
        if snapshot_date:
            stmt = stmt.where(ReconciliationSnapshot.snapshot_date == snapshot_date)
        if currency:
            stmt = stmt.where(ReconciliationSnapshot.currency == currency.upper())
        rows = self.db.execute(stmt).all()
        return [self._serialize_reconciliation_snapshot(snapshot, account) for snapshot, account in rows]

    def build_country_revenue_snapshots(
        self,
        *,
        period_key: str | None = None,
        country_code: str | None = None,
    ) -> list[dict[str, object]]:
        target_period = period_key or datetime.now(timezone.utc).strftime("%Y-%m")
        # Include both the current social-split releases ("escrow_release:%", which also
        # carries the legacy pre-2026-06 tasker-net credit) and the legacy ZASKA 15%
        # commission credits ("commission:%"), which used a separate transaction/reference.
        # Without "commission:%", legacy ZASKA revenue would be silently absent from
        # country revenue snapshots — see SOCIAL_SPLIT_MODEL / LEGACY_SPLIT_MODEL.
        rows = self.db.execute(
            select(Transaction, Wallet)
            .join(Wallet, Wallet.id == Transaction.wallet_id)
            .where(
                Transaction.status == "completed",
                Transaction.type == "credit",
                (
                    Transaction.reference.like("escrow_release:%")
                    | Transaction.reference.like("commission:%")
                ),
            )
            .order_by(Transaction.created_at.asc())
        ).all()

        task_context = self._build_task_context([
            self.wallet_service._parse_metadata(tx).get("task_id")
            for tx, _wallet in rows
        ])

        aggregates: dict[tuple[str, str], dict[str, object]] = {}
        seen_tasks: dict[tuple[str, str], set[str]] = defaultdict(set)
        split_models_seen: dict[tuple[str, str], set[str]] = defaultdict(set)

        for tx, wallet in rows:
            created_at = tx.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            tx_period = created_at.strftime("%Y-%m")
            if tx_period != target_period:
                continue

            metadata = self.wallet_service._parse_metadata(tx)
            split_line = str(metadata.get("split_line") or "")

            if split_line in SOCIAL_SPLIT_LINES:
                split_model = SOCIAL_SPLIT_MODEL
                revenue_bucket_key = split_line
            elif tx.reference.startswith("escrow_release:") and "commission_bps" in metadata:
                # Legacy tasker-net credit (85% of gross) — no split_line, "net"/"commission_bps" metadata.
                split_model = LEGACY_SPLIT_MODEL
                revenue_bucket_key = "tasker_net"
            elif tx.reference.startswith("commission:") and metadata.get("type") == "zaska_commission":
                # Legacy ZASKA commission credit (15% of gross), separate transaction.
                split_model = LEGACY_SPLIT_MODEL
                revenue_bucket_key = "zaska_operations"
            else:
                continue

            task_id = str(metadata.get("task_id") or "") or None
            resolved_country = self._resolve_country_code(task_id=task_id, task_context=task_context, metadata=metadata)
            if country_code and resolved_country != country_code.upper():
                continue
            bucket_key = (resolved_country, wallet.currency)
            bucket = aggregates.setdefault(
                bucket_key,
                {
                    "country_code": resolved_country,
                    "currency": wallet.currency,
                    "gross_task_volume": _ZERO,
                    "tasker_net_total": _ZERO,
                    "zaska_revenue_total": _ZERO,
                    "pension_total": _ZERO,
                    "health_total": _ZERO,
                    "smoothing_total": _ZERO,
                    "completed_tasks_count": 0,
                    "source_tx_count": 0,
                },
            )
            amount = Decimal(str(tx.amount))
            if revenue_bucket_key == "tasker_net":
                bucket["tasker_net_total"] += amount
            elif revenue_bucket_key == "zaska_operations":
                bucket["zaska_revenue_total"] += amount
            elif revenue_bucket_key == "pension_fund":
                bucket["pension_total"] += amount
            elif revenue_bucket_key == "health_fund":
                bucket["health_total"] += amount
            elif revenue_bucket_key == "smoothing_fund":
                bucket["smoothing_total"] += amount

            bucket["source_tx_count"] += 1
            split_models_seen[bucket_key].add(split_model)
            # Only count gross task volume / completed tasks once per task, from the
            # tasker-net leg (present in both the social_v2 and legacy models).
            if revenue_bucket_key == "tasker_net" and task_id and task_id not in seen_tasks[bucket_key]:
                gross = Decimal(str(metadata.get("gross") or "0"))
                bucket["gross_task_volume"] += gross
                bucket["completed_tasks_count"] += 1
                seen_tasks[bucket_key].add(task_id)

        snapshots: list[dict[str, object]] = []
        for (resolved_country, snapshot_currency), payload in sorted(aggregates.items()):
            row = self.db.execute(
                select(CountryRevenueSnapshot).where(
                    CountryRevenueSnapshot.period_key == target_period,
                    CountryRevenueSnapshot.country_code == resolved_country,
                    CountryRevenueSnapshot.currency == snapshot_currency,
                )
            ).scalars().one_or_none()
            metadata_json = json.dumps(
                {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "source_tx_count": payload["source_tx_count"],
                    "split_models_included": sorted(split_models_seen[(resolved_country, snapshot_currency)]),
                }
            )
            if row is None:
                row = CountryRevenueSnapshot(
                    id=_uuid(),
                    period_key=target_period,
                    country_code=resolved_country,
                    currency=snapshot_currency,
                    gross_task_volume=payload["gross_task_volume"],
                    tasker_net_total=payload["tasker_net_total"],
                    zaska_revenue_total=payload["zaska_revenue_total"],
                    pension_total=payload["pension_total"],
                    health_total=payload["health_total"],
                    smoothing_total=payload["smoothing_total"],
                    completed_tasks_count=int(payload["completed_tasks_count"]),
                    metadata_json=metadata_json,
                )
                self.db.add(row)
            else:
                row.gross_task_volume = payload["gross_task_volume"]
                row.tasker_net_total = payload["tasker_net_total"]
                row.zaska_revenue_total = payload["zaska_revenue_total"]
                row.pension_total = payload["pension_total"]
                row.health_total = payload["health_total"]
                row.smoothing_total = payload["smoothing_total"]
                row.completed_tasks_count = int(payload["completed_tasks_count"])
                row.metadata_json = metadata_json
            snapshots.append(self._serialize_country_revenue_snapshot(row))

        self.db.commit()
        return snapshots

    def list_country_revenue_snapshots(
        self,
        *,
        period_key: str | None = None,
        country_code: str | None = None,
        currency: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, object]]:
        stmt = select(CountryRevenueSnapshot).order_by(
            CountryRevenueSnapshot.period_key.desc(),
            CountryRevenueSnapshot.country_code.asc(),
            CountryRevenueSnapshot.currency.asc(),
        ).limit(limit)
        if period_key:
            stmt = stmt.where(CountryRevenueSnapshot.period_key == period_key)
        if country_code:
            stmt = stmt.where(CountryRevenueSnapshot.country_code == country_code.upper())
        if currency:
            stmt = stmt.where(CountryRevenueSnapshot.currency == currency.upper())
        rows = self.db.execute(stmt).scalars().all()
        return [self._serialize_country_revenue_snapshot(row) for row in rows]

    def get_ledger_overview(self) -> dict[str, object]:
        self.seed_chart_of_accounts()
        accounts = self.db.execute(
            select(FinancialAccount).where(FinancialAccount.is_active.is_(True))
        ).scalars().all()
        balances = self._ledger_balances_map([account.id for account in accounts])
        by_currency: dict[str, dict[str, str]] = defaultdict(dict)
        for account in accounts:
            if not account.currency:
                continue
            by_currency[account.currency][account.code] = str(balances.get(account.id, _ZERO))

        latest_reconciliation = self.db.execute(
            select(func.max(ReconciliationSnapshot.snapshot_date))
        ).scalar()
        latest_country_period = self.db.execute(
            select(func.max(CountryRevenueSnapshot.period_key))
        ).scalar()
        entry_count = self.db.execute(select(func.count(LedgerEntry.id))).scalar() or 0

        return {
            "accounts_count": len(accounts),
            "ledger_entries_count": int(entry_count),
            "currencies": dict(by_currency),
            "latest_reconciliation_date": latest_reconciliation.isoformat() if latest_reconciliation else None,
            "latest_country_revenue_period": str(latest_country_period) if latest_country_period else None,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def sync_restaurant_payout_snapshots(
        self,
        *,
        period_key: str | None = None,
        restaurant_id: str | None = None,
    ) -> dict[str, object]:
        self.seed_chart_of_accounts()
        stmt = (
            select(RestaurantPayoutSnapshot, RestaurantPartner)
            .join(RestaurantPartner, RestaurantPartner.id == RestaurantPayoutSnapshot.restaurant_id)
            .order_by(RestaurantPayoutSnapshot.period_key.asc(), RestaurantPartner.public_name.asc())
        )
        if period_key:
            stmt = stmt.where(RestaurantPayoutSnapshot.period_key == period_key)
        if restaurant_id:
            stmt = stmt.where(RestaurantPayoutSnapshot.restaurant_id == restaurant_id)
        rows = self.db.execute(stmt).all()

        created = 0
        for snapshot, restaurant in rows:
            released_account = self._get_or_create_account("RESTAURANT_PAYOUTS_RELEASED", snapshot.currency)
            pending_account = self._get_or_create_account("RESTAURANT_PAYOUTS_PENDING", snapshot.currency)
            refunded_account = self._get_or_create_account("RESTAURANT_PAYOUTS_REFUNDED", snapshot.currency)
            journal_id = f"restaurant-payout:{snapshot.period_key}:{snapshot.restaurant_id}:{snapshot.currency}"
            base_meta = {
                "restaurant_id": snapshot.restaurant_id,
                "restaurant_name": restaurant.public_name,
                "period_key": snapshot.period_key,
                "currency": snapshot.currency,
            }
            if snapshot.released_payout_total > _ZERO:
                created += int(
                    self._insert_ledger_entry(
                        account=released_account,
                        direction="credit",
                        amount=Decimal(str(snapshot.released_payout_total)),
                        currency=snapshot.currency,
                        reference=f"{journal_id}:released",
                        source_table="restaurant_payout_snapshots",
                        source_id=snapshot.id,
                        country_code=restaurant.country_code,
                        module_code="FOOD",
                        entry_type="restaurant_payout_snapshot_released",
                        journal_id=journal_id,
                        metadata=base_meta,
                        created_at=snapshot.created_at,
                    )
                )
            if snapshot.pending_meal_total > _ZERO:
                created += int(
                    self._insert_ledger_entry(
                        account=pending_account,
                        direction="credit",
                        amount=Decimal(str(snapshot.pending_meal_total)),
                        currency=snapshot.currency,
                        reference=f"{journal_id}:pending",
                        source_table="restaurant_payout_snapshots",
                        source_id=snapshot.id,
                        country_code=restaurant.country_code,
                        module_code="FOOD",
                        entry_type="restaurant_payout_snapshot_pending",
                        journal_id=journal_id,
                        metadata=base_meta,
                        created_at=snapshot.created_at,
                    )
                )
            if snapshot.refunded_meal_total > _ZERO:
                created += int(
                    self._insert_ledger_entry(
                        account=refunded_account,
                        direction="credit",
                        amount=Decimal(str(snapshot.refunded_meal_total)),
                        currency=snapshot.currency,
                        reference=f"{journal_id}:refunded",
                        source_table="restaurant_payout_snapshots",
                        source_id=snapshot.id,
                        country_code=restaurant.country_code,
                        module_code="FOOD",
                        entry_type="restaurant_payout_snapshot_refunded",
                        journal_id=journal_id,
                        metadata=base_meta,
                        created_at=snapshot.created_at,
                    )
                )

        self.db.commit()
        return {
            "snapshots_scanned": len(rows),
            "ledger_entries_created": created,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _known_currencies(self) -> list[str]:
        currencies = {"XOF", "EUR", "USD", "GHS", "NGN", "GBP", "CAD"}
        wallet_rows = self.db.execute(select(Wallet.currency).distinct()).all()
        country_rows = self.db.execute(select(Country.currency_code).distinct()).all()
        for row in wallet_rows + country_rows:
            if row[0]:
                currencies.add(str(row[0]).upper())
        return sorted(currencies)

    def _resolve_owner_user_id(self, owner_setting: object) -> str | None:
        if not owner_setting:
            return None
        value = getattr(settings, str(owner_setting), "")
        return str(value).strip() or None

    def _find_account(self, code: str, currency: str) -> FinancialAccount | None:
        return self.db.execute(
            select(FinancialAccount).where(
                FinancialAccount.code == code.upper(),
                FinancialAccount.currency == currency.upper(),
            )
        ).scalars().one_or_none()

    def _get_or_create_account(self, code: str, currency: str) -> FinancialAccount:
        account = self._find_account(code.upper(), currency.upper())
        if account is not None:
            return account
        config = self.DEFAULT_ACCOUNT_DEFINITIONS[code.upper()]
        account = FinancialAccount(
            id=_uuid(),
            code=code.upper(),
            label=str(config["label"]),
            account_type=str(config["account_type"]),
            scope_type="global",
            scope_value="*",
            module_code=str(config["module_code"]),
            currency=currency.upper(),
            owner_user_id=self._resolve_owner_user_id(config.get("owner_setting")),
            is_system=True,
            is_active=True,
            metadata_json=json.dumps({"seeded": True, "lazy_created": True}),
        )
        self.db.add(account)
        self.db.flush()
        self._ensure_global_scope(account)
        return account

    def _ensure_global_scope(self, account: FinancialAccount) -> bool:
        existing = self.db.execute(
            select(FinancialAccountScope).where(
                FinancialAccountScope.account_id == account.id,
                FinancialAccountScope.scope_type == "global",
                FinancialAccountScope.scope_value == "*",
            )
        ).scalars().one_or_none()
        if existing is not None:
            if not existing.is_active:
                existing.is_active = True
                return True
            return False
        self.db.add(
            FinancialAccountScope(
                id=_uuid(),
                account_id=account.id,
                scope_type="global",
                scope_value="*",
                module_code=account.module_code,
                is_active=True,
            )
        )
        self.db.flush()
        return True

    def _system_owner_to_account_code(self) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for setting_name, code in self.SYSTEM_ACCOUNT_CODE_BY_SETTING.items():
            owner_user_id = self._resolve_owner_user_id(setting_name)
            if owner_user_id:
                mapping[owner_user_id] = code
        return mapping

    def _build_task_context(self, raw_task_ids: list[object]) -> dict[str, dict[str, str | None]]:
        task_ids = sorted({str(task_id) for task_id in raw_task_ids if task_id})
        if not task_ids:
            return {}
        tasks = self.db.execute(select(Task).where(Task.id.in_(task_ids))).scalars().all()
        creator_ids = {task.created_by for task in tasks if task.created_by}
        users = {}
        if creator_ids:
            users = {
                user.id: user
                for user in self.db.execute(select(User).where(User.id.in_(creator_ids))).scalars().all()
            }
        context: dict[str, dict[str, str | None]] = {}
        for task in tasks:
            creator = users.get(task.created_by)
            context[task.id] = {
                "task_country_name": task.country,
                "task_city_name": task.city,
                "creator_country_code": creator.country_code if creator else None,
            }
        return context

    def _resolve_country_code(
        self,
        *,
        task_id: str | None,
        task_context: dict[str, dict[str, str | None]],
        metadata: dict[str, object],
    ) -> str:
        if task_id and task_id in task_context:
            creator_country_code = task_context[task_id].get("creator_country_code")
            if creator_country_code:
                return str(creator_country_code).upper()
        country_meta = metadata.get("country_code")
        if country_meta:
            return str(country_meta).upper()
        return "UNSPECIFIED"

    def _insert_ledger_entry(
        self,
        *,
        account: FinancialAccount,
        direction: str,
        amount: Decimal,
        currency: str,
        reference: str,
        source_table: str,
        source_id: str,
        country_code: str | None,
        module_code: str | None,
        entry_type: str,
        journal_id: str,
        metadata: dict[str, object],
        created_at: datetime | None,
    ) -> bool:
        existing = self.db.execute(
            select(LedgerEntry).where(
                LedgerEntry.reference == reference,
                LedgerEntry.account_id == account.id,
                LedgerEntry.direction == direction,
            )
        ).scalars().one_or_none()
        if existing is not None:
            return False

        entry_created_at = created_at or datetime.now(timezone.utc)
        if entry_created_at.tzinfo is None:
            entry_created_at = entry_created_at.replace(tzinfo=timezone.utc)

        self.db.add(
            LedgerEntry(
                id=_uuid(),
                journal_id=journal_id,
                account_id=account.id,
                direction=direction,
                amount=amount,
                currency=currency.upper(),
                reference=reference,
                source_table=source_table,
                source_id=source_id,
                country_code=country_code,
                module_code=module_code,
                entry_type=entry_type,
                metadata_json=json.dumps(metadata),
                created_at=entry_created_at,
            )
        )
        return True

    def _journal_id_for_transaction(self, reference: str, metadata: dict[str, object]) -> str:
        escrow_id = metadata.get("escrow_id")
        if escrow_id:
            return str(escrow_id)
        task_id = metadata.get("task_id")
        if task_id:
            return str(task_id)
        return reference

    def _account_module_code(self, account_code: str) -> str | None:
        config = self.DEFAULT_ACCOUNT_DEFINITIONS.get(account_code)
        if not config:
            return None
        return str(config["module_code"])

    def _ledger_balance_for_account(self, account_id: str) -> Decimal:
        balance = self.db.execute(
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (LedgerEntry.direction == "credit", LedgerEntry.amount),
                            else_=-LedgerEntry.amount,
                        )
                    ),
                    _ZERO,
                )
            ).where(LedgerEntry.account_id == account_id)
        ).scalar()
        return Decimal(str(balance)) if balance is not None else _ZERO

    def _ledger_balances_map(self, account_ids: list[str]) -> dict[str, Decimal]:
        if not account_ids:
            return {}
        rows = self.db.execute(
            select(
                LedgerEntry.account_id,
                func.coalesce(
                    func.sum(
                        case(
                            (LedgerEntry.direction == "credit", LedgerEntry.amount),
                            else_=-LedgerEntry.amount,
                        )
                    ),
                    _ZERO,
                ).label("balance"),
            )
            .where(LedgerEntry.account_id.in_(account_ids))
            .group_by(LedgerEntry.account_id)
        ).all()
        return {row.account_id: Decimal(str(row.balance)) for row in rows}

    def _source_wallet_balance(self, owner_user_id: str | None, currency: str) -> Decimal:
        if not owner_user_id:
            return _ZERO
        try:
            return self.wallet_service.get_balance(owner_user_id, currency)
        except Exception as exc:
            logger.warning(
                "accounting_source_wallet_balance_unavailable user_id={} currency={} error={}",
                owner_user_id,
                currency,
                exc,
            )
            return _ZERO

    def _serialize_account(self, account: FinancialAccount, balance: Decimal) -> dict[str, object]:
        return {
            "id": account.id,
            "code": account.code,
            "label": account.label,
            "account_type": account.account_type,
            "scope_type": account.scope_type,
            "scope_value": account.scope_value,
            "module_code": account.module_code,
            "currency": account.currency,
            "owner_user_id": account.owner_user_id,
            "is_system": bool(account.is_system),
            "is_active": bool(account.is_active),
            "ledger_balance": str(balance),
            "created_at": account.created_at.isoformat() if account.created_at else None,
            "updated_at": account.updated_at.isoformat() if account.updated_at else None,
        }

    def _serialize_reconciliation_snapshot(
        self,
        snapshot: ReconciliationSnapshot,
        account: FinancialAccount,
    ) -> dict[str, object]:
        return {
            "id": snapshot.id,
            "snapshot_date": snapshot.snapshot_date.isoformat(),
            "currency": snapshot.currency,
            "account_id": account.id,
            "account_code": account.code,
            "account_label": account.label,
            "owner_user_id": account.owner_user_id,
            "ledger_balance": str(snapshot.ledger_balance),
            "source_wallet_balance": str(snapshot.source_wallet_balance),
            "drift_amount": str(snapshot.drift_amount),
            "status": snapshot.status,
            "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
        }

    def _serialize_country_revenue_snapshot(self, snapshot: CountryRevenueSnapshot) -> dict[str, object]:
        return {
            "id": snapshot.id,
            "period_key": snapshot.period_key,
            "country_code": snapshot.country_code,
            "currency": snapshot.currency,
            "gross_task_volume": str(snapshot.gross_task_volume),
            "tasker_net_total": str(snapshot.tasker_net_total),
            "zaska_revenue_total": str(snapshot.zaska_revenue_total),
            "pension_total": str(snapshot.pension_total),
            "health_total": str(snapshot.health_total),
            "smoothing_total": str(snapshot.smoothing_total),
            "completed_tasks_count": int(snapshot.completed_tasks_count),
            "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
        }
