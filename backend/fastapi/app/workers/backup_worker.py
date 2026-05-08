"""
PostgreSQL automated backup Celery task.

Runs daily via beat schedule. Uses pg_dump to create compressed backups
in BACKUP_DIR, and rotates files older than BACKUP_KEEP_DAYS.
"""

from __future__ import annotations

import gzip
import logging
import os
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import settings
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


def _parse_db_url(url: str) -> dict:
    parsed = urlparse(url)
    return {
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 5432),
        "user": parsed.username or "postgres",
        "password": parsed.password or "",
        "dbname": (parsed.path or "/zaska").lstrip("/"),
    }


@celery_app.task(name="app.workers.backup_worker.backup_postgres", bind=True)
def backup_postgres(self):
    """
    Daily scheduled task — dumps the PostgreSQL database to a gzipped file.
    Rotates backups older than settings.backup_keep_days.
    """
    backup_dir = Path(settings.backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)

    db = _parse_db_url(settings.database_url)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    dump_path = backup_dir / f"zaska_{timestamp}.sql.gz"

    env = os.environ.copy()
    if db["password"]:
        env["PGPASSWORD"] = db["password"]

    pg_dump_cmd = shutil.which("pg_dump")
    if pg_dump_cmd is None:
        logger.warning("backup_postgres: pg_dump not found in PATH — skipping backup")
        return {"status": "skipped", "reason": "pg_dump not found"}

    try:
        proc = subprocess.run(
            [
                pg_dump_cmd,
                "-h", db["host"],
                "-p", db["port"],
                "-U", db["user"],
                "-d", db["dbname"],
                "--no-password",
                "-Fp",
            ],
            env=env,
            capture_output=True,
            timeout=300,
        )

        if proc.returncode != 0:
            err = proc.stderr.decode(errors="replace")[:500]
            logger.error("backup_postgres: pg_dump failed (rc=%s): %s", proc.returncode, err)
            raise RuntimeError(f"pg_dump rc={proc.returncode}: {err}")

        with gzip.open(dump_path, "wb") as gz:
            gz.write(proc.stdout)

        size_mb = dump_path.stat().st_size / (1024 * 1024)
        logger.info("backup_postgres: created %s (%.1f MB)", dump_path.name, size_mb)

        # Rotate old backups
        cutoff = datetime.utcnow() - timedelta(days=settings.backup_keep_days)
        removed = 0
        for f in backup_dir.glob("zaska_*.sql.gz"):
            if datetime.utcfromtimestamp(f.stat().st_mtime) < cutoff:
                f.unlink()
                removed += 1
                logger.info("backup_postgres: rotated old backup %s", f.name)

        return {
            "status": "ok",
            "file": dump_path.name,
            "size_mb": round(size_mb, 2),
            "rotated": removed,
        }

    except subprocess.TimeoutExpired:
        logger.error("backup_postgres: pg_dump timed out after 300s")
        raise self.retry(exc=RuntimeError("pg_dump timeout"), countdown=3600) from None
    except Exception as exc:
        logger.error("backup_postgres: failed — %s", exc)
        raise self.retry(exc=exc, countdown=3600) from exc
