"""文件上传API路由"""
import os
import re
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, RedirectResponse

from ..models.user import User
from ..services.storage_service import LocalStorageProvider, get_storage_provider
from ..utils.deps import get_current_user

router = APIRouter(prefix="/upload", tags=["文件上传"])

# 上传目录配置
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
AVATAR_DIR = os.path.join(UPLOAD_DIR, "avatars")
IMAGE_DIR = os.path.join(UPLOAD_DIR, "images")
FILE_DIR = os.path.join(UPLOAD_DIR, "files")

# 确保目录存在
try:
    if isinstance(get_storage_provider(), LocalStorageProvider):
        os.makedirs(AVATAR_DIR, exist_ok=True)
        os.makedirs(IMAGE_DIR, exist_ok=True)
        os.makedirs(FILE_DIR, exist_ok=True)
except Exception:
    pass

# 允许的图片类型
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB

ALLOWED_FILE_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/json",
    "application/zip",
    "application/x-zip-compressed",
    "application/x-7z-compressed",
    "application/x-rar-compressed",
    "application/vnd.rar",
    "application/x-tar",
    "application/gzip",
    "application/x-gzip",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "audio/mpeg",
    "audio/wav",
    "audio/ogg",
    "audio/mp4",
    "video/mp4",
    "video/webm",
    "video/ogg",
}

MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024

_AVATAR_FILENAME_RE = re.compile(r"^\d+_[0-9a-f]{8}_\d+\.(jpg|jpeg|png|gif|webp)$", re.IGNORECASE)
_IMAGE_FILENAME_RE = re.compile(r"^[0-9a-f]{32}\.(jpg|jpeg|png|gif|webp)$", re.IGNORECASE)
_FILE_FILENAME_RE = re.compile(r"^[0-9a-f]{32}\.[a-z0-9]{1,10}$", re.IGNORECASE)


def _detect_image_ext(content: bytes) -> str | None:
    if len(content) < 12:
        return None

    if content[:3] == b"\xFF\xD8\xFF":
        return "jpg"
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if content[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    # WEBP: RIFF....WEBP
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "webp"
    return None


def _is_safe_filename(filename: str) -> bool:
    if not filename:
        return False
    if filename != os.path.basename(filename):
        return False
    if ".." in filename or "/" in filename or "\\" in filename:
        return False
    return _AVATAR_FILENAME_RE.match(filename) is not None


def _is_safe_image_filename(filename: str) -> bool:
    if not filename:
        return False
    if filename != os.path.basename(filename):
        return False
    if ".." in filename or "/" in filename or "\\" in filename:
        return False
    return _IMAGE_FILENAME_RE.match(filename) is not None


def _is_safe_file_filename(filename: str) -> bool:
    if not filename:
        return False
    if filename != os.path.basename(filename):
        return False
    if ".." in filename or "/" in filename or "\\" in filename:
        return False
    return _FILE_FILENAME_RE.match(filename) is not None


@router.post("/avatar", summary="上传头像")
async def upload_avatar(
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    上传用户头像
    
    - 支持 jpg, png, gif, webp 格式
    - 最大 2MB
    """
    # 检查文件类型
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail="不支持的图片格式，请上传 jpg/png/gif/webp 格式"
        )
    
    # 读取文件内容
    content = await file.read()

    detected_ext = _detect_image_ext(content)
    if detected_ext is None:
        raise HTTPException(
            status_code=400,
            detail="无法识别图片格式，请上传 jpg/png/gif/webp 格式"
        )
    
    # 检查文件大小
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail="图片大小不能超过 2MB"
        )
    
    # 生成唯一文件名
    filename = f"{current_user.id}_{uuid.uuid4().hex[:8]}_{int(datetime.now().timestamp())}.{detected_ext}"
    storage = get_storage_provider()
    
    # 删除旧头像文件（如果存在且是本地文件）
    current_avatar = getattr(current_user, "avatar", None)
    if isinstance(storage, LocalStorageProvider):
        if current_avatar and isinstance(current_avatar, str) and current_avatar.startswith("/api/upload/avatars/"):
            old_filename = current_avatar.split("/")[-1]
            old_filepath = storage.get_local_path(category="avatars", filename=old_filename)
            if os.path.exists(old_filepath):
                try:
                    os.remove(old_filepath)
                except Exception:
                    pass
    
    await storage.put_bytes(
        category="avatars",
        filename=filename,
        content=content,
        content_type=file.content_type,
    )
    
    # 返回访问URL
    avatar_url = f"/api/upload/avatars/{filename}"
    
    return {
        "url": avatar_url,
        "filename": filename,
        "message": "头像上传成功"
    }


@router.get("/avatars/{filename}", summary="获取头像")
async def get_avatar(filename: str):
    """获取头像文件"""
    if not _is_safe_filename(filename):
        raise HTTPException(status_code=400, detail="非法文件名")
    storage = get_storage_provider()
    if isinstance(storage, LocalStorageProvider):
        filepath = storage.get_local_path(category="avatars", filename=filename)
        if not os.path.exists(filepath):
            raise HTTPException(status_code=404, detail="文件不存在")
        return FileResponse(filepath)

    url = await storage.get_download_url(category="avatars", filename=filename)
    return RedirectResponse(url=url, status_code=307)


@router.post("/file", summary="上传附件")
async def upload_file(
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    _ = current_user

    if file.content_type not in ALLOWED_FILE_TYPES:
        raise HTTPException(status_code=400, detail="不支持的文件类型")

    content = await file.read()
    if len(content) > MAX_ATTACHMENT_SIZE:
        raise HTTPException(status_code=400, detail="文件大小不能超过 10MB")

    original_name = os.path.basename(file.filename or "")
    original_name = original_name.strip() or "attachment"

    ext = os.path.splitext(original_name)[1].lstrip(".").lower()
    if not ext:
        raise HTTPException(status_code=400, detail="无法识别文件扩展名")

    filename = f"{uuid.uuid4().hex}.{ext}"
    storage = get_storage_provider()
    await storage.put_bytes(
        category="files",
        filename=filename,
        content=content,
        content_type=file.content_type,
    )

    file_url = f"/api/upload/files/{filename}"
    return {
        "url": file_url,
        "filename": filename,
        "original_name": original_name,
        "message": "上传成功",
    }


@router.get("/files/{filename}", summary="获取附件")
async def get_file(filename: str):
    if not _is_safe_file_filename(filename):
        raise HTTPException(status_code=400, detail="非法文件名")
    storage = get_storage_provider()
    if isinstance(storage, LocalStorageProvider):
        filepath = storage.get_local_path(category="files", filename=filename)
        if not os.path.exists(filepath):
            raise HTTPException(status_code=404, detail="文件不存在")
        return FileResponse(filepath)

    url = await storage.get_download_url(category="files", filename=filename)
    return RedirectResponse(url=url, status_code=307)


@router.post("/image", summary="上传图片")
async def upload_image(
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """上传通用图片（需登录）"""
    _ = current_user

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail="不支持的图片格式，请上传 jpg/png/gif/webp 格式",
        )

    content = await file.read()

    detected_ext = _detect_image_ext(content)
    if detected_ext is None:
        raise HTTPException(
            status_code=400,
            detail="无法识别图片格式，请上传 jpg/png/gif/webp 格式",
        )

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail="图片大小不能超过 2MB",
        )

    filename = f"{uuid.uuid4().hex}.{detected_ext}"
    storage = get_storage_provider()
    await storage.put_bytes(
        category="images",
        filename=filename,
        content=content,
        content_type=file.content_type,
    )

    image_url = f"/api/upload/images/{filename}"

    return {
        "url": image_url,
        "filename": filename,
        "message": "图片上传成功",
    }


@router.get("/images/{filename}", summary="获取图片")
async def get_image(filename: str):
    """获取图片文件"""
    if not _is_safe_image_filename(filename):
        raise HTTPException(status_code=400, detail="非法文件名")
    storage = get_storage_provider()
    if isinstance(storage, LocalStorageProvider):
        filepath = storage.get_local_path(category="images", filename=filename)
        if not os.path.exists(filepath):
            raise HTTPException(status_code=404, detail="文件不存在")
        return FileResponse(filepath)

    url = await storage.get_download_url(category="images", filename=filename)
    return RedirectResponse(url=url, status_code=307)
