import cloudinary
import cloudinary.uploader

from app.core.config import settings


def _configure() -> None:
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )


def is_configured() -> bool:
    return bool(
        settings.cloudinary_cloud_name.strip()
        and settings.cloudinary_api_key.strip()
        and settings.cloudinary_api_secret.strip()
    )


async def upload_kyc_document(data: bytes, content_type: str, public_id: str) -> str:
    _configure()
    resource_type = "raw" if content_type == "application/pdf" else "image"
    result = cloudinary.uploader.upload(
        data,
        resource_type=resource_type,
        folder="kyc",
        public_id=public_id,
        overwrite=False,
        invalidate=True,
    )
    return result["secure_url"]
