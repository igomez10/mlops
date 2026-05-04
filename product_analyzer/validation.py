from __future__ import annotations

from fastapi import HTTPException, UploadFile

ALLOWED_MIME_TYPES = frozenset({"image/jpeg", "image/png"})
MAX_IMAGE_BYTES = 12 * 1024 * 1024  # 12 MB


async def validate_image(upload: UploadFile) -> tuple[bytes, str]:
    """Read and validate an uploaded image. Returns (raw_bytes, normalized_mime)."""
    mime = (upload.content_type or "").split(";")[0].strip().lower()
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Only image/jpeg and image/png are supported.",
        )
    data = await upload.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Image too large (max {MAX_IMAGE_BYTES // (1024 * 1024)} MB).",
        )
    return data, mime
