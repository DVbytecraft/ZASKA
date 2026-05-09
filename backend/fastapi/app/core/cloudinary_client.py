import mimetypes
import cloudinary
import cloudinary.uploader

from app.core.config import settings

# MIME types allowed for chat media attachments
_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
_ALLOWED_VIDEO_TYPES = {"video/mp4", "video/webm", "video/quicktime"}
_ALLOWED_DOC_TYPES   = {"application/pdf"}
ALLOWED_CHAT_TYPES   = _ALLOWED_IMAGE_TYPES | _ALLOWED_VIDEO_TYPES | _ALLOWED_DOC_TYPES

# Upload size caps (bytes)
CHAT_IMAGE_MAX_BYTES = 10 * 1024 * 1024   # 10 MB
CHAT_VIDEO_MAX_BYTES = 50 * 1024 * 1024   # 50 MB
CHAT_DOC_MAX_BYTES   =  5 * 1024 * 1024   #  5 MB


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


def _resource_type(content_type: str) -> str:
    if content_type in _ALLOWED_VIDEO_TYPES:
        return "video"
    if content_type in _ALLOWED_DOC_TYPES:
        return "raw"
    return "image"


def chat_size_limit(content_type: str) -> int:
    if content_type in _ALLOWED_VIDEO_TYPES:
        return CHAT_VIDEO_MAX_BYTES
    if content_type in _ALLOWED_DOC_TYPES:
        return CHAT_DOC_MAX_BYTES
    return CHAT_IMAGE_MAX_BYTES


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


async def upload_chat_media(
    data: bytes,
    content_type: str,
    task_id: str,
    sender_id: str,
) -> dict:
    """
    Upload a chat attachment to Cloudinary.
    Returns {"secure_url": str, "resource_type": str, "media_type": str}
    """
    _configure()
    rtype = _resource_type(content_type)
    ext = mimetypes.guess_extension(content_type) or ""
    public_id = f"chat/{task_id}/{sender_id}_{cloudinary.utils.now()}{ext}"

    result = cloudinary.uploader.upload(
        data,
        resource_type=rtype,
        folder="chat",
        public_id=public_id,
        overwrite=False,
        invalidate=True,
        # Restrict delivery to signed URLs for privacy
        type="authenticated" if rtype != "video" else "upload",
    )
    # Determine display media_type for frontend
    if content_type in _ALLOWED_IMAGE_TYPES:
        media_type = "image"
    elif content_type in _ALLOWED_VIDEO_TYPES:
        media_type = "video"
    else:
        media_type = "document"

    return {
        "secure_url": result["secure_url"],
        "resource_type": rtype,
        "media_type": media_type,
        "bytes": result.get("bytes", len(data)),
        "format": result.get("format", ""),
    }
