"""
FCM push notification service.

Sends push notifications via Firebase Cloud Messaging HTTP v1 API.
If FCM credentials are not configured, falls back to a no-op (log only).
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class PushService:
    """
    Wrapper around FCM HTTP v1 API.
    Requires google-auth package (included in requirements.txt).
    """

    def __init__(self, service_account_path: str, project_id: str):
        self._service_account_path = service_account_path
        self._project_id = project_id
        self._credentials = None
        self._enabled = bool(service_account_path and Path(service_account_path).is_file())

        if not self._enabled:
            logger.warning(
                "PushService: FCM disabled — set FCM_SERVICE_ACCOUNT_PATH to enable push notifications"
            )

    def _get_access_token(self) -> Optional[str]:
        try:
            import google.auth.transport.requests  # type: ignore
            import google.oauth2.service_account  # type: ignore

            if self._credentials is None:
                self._credentials = (
                    google.oauth2.service_account.Credentials.from_service_account_file(
                        self._service_account_path,
                        scopes=["https://www.googleapis.com/auth/firebase.messaging"],
                    )
                )

            request = google.auth.transport.requests.Request()
            self._credentials.refresh(request)
            return self._credentials.token
        except Exception as exc:
            logger.error("PushService: failed to get FCM access token — %s", exc)
            return None

    def _resolve_project_id(self) -> str:
        if self._project_id:
            return self._project_id
        try:
            with open(self._service_account_path) as f:
                data = json.load(f)
            return data.get("project_id", "")
        except Exception:
            return ""

    def send(self, fcm_token: str, title: str, body: str, data: dict | None = None) -> bool:
        """
        Send a push notification to a single device token.
        Returns True on success, False on failure.
        """
        if not self._enabled:
            logger.info("PushService: [no-op] title=%r body=%r token=%s…", title, body, fcm_token[:16])
            return False

        access_token = self._get_access_token()
        if not access_token:
            return False

        project_id = self._resolve_project_id()
        if not project_id:
            logger.error("PushService: project_id not found in service account file")
            return False

        import urllib.error
        import urllib.request

        url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
        message: dict = {
            "message": {
                "token": fcm_token,
                "notification": {"title": title, "body": body},
            }
        }
        if data:
            message["message"]["data"] = {k: str(v) for k, v in data.items()}

        payload = json.dumps(message).encode()
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                logger.info(
                    "PushService: sent push notification to %s… (status=%s)",
                    fcm_token[:16], resp.status,
                )
            return True
        except urllib.error.HTTPError as exc:
            body_err = exc.read().decode(errors="replace")[:300]
            logger.error("PushService: FCM HTTP error %s — %s", exc.code, body_err)
            return False
        except Exception as exc:
            logger.error("PushService: failed to send push — %s", exc)
            return False


@lru_cache(maxsize=1)
def get_push_service() -> PushService:
    from app.core.config import settings
    return PushService(
        service_account_path=settings.fcm_service_account_path,
        project_id=settings.fcm_project_id,
    )
