from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import require_admin, get_feature_flag_service
from app.core.responses import success_response
from app.schemas.feature_flag import FeatureFlagPayload
from app.services.feature_flag_service import FeatureFlagService

router = APIRouter(prefix="/feature-flags", tags=["feature-flags"])


@router.get("")
def list_flags(
    country_id: str | None = None,
    service: FeatureFlagService = Depends(get_feature_flag_service),
    _admin: str = Depends(require_admin),
):
    try:
        flags = service.list_flags(country_id=country_id)
        return success_response(
            [{"id": f.id, "feature": f.feature, "countryId": f.country_id, "enabled": f.enabled} for f in flags]
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to list feature flags") from exc


@router.post("")
def upsert_flag(
    payload: FeatureFlagPayload,
    service: FeatureFlagService = Depends(get_feature_flag_service),
    _admin: str = Depends(require_admin),
):
    try:
        flag = service.upsert_flag(payload.feature, payload.country_id, payload.enabled)
        return success_response({"id": flag.id, "feature": flag.feature, "countryId": flag.country_id, "enabled": flag.enabled})
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to save feature flag") from exc
