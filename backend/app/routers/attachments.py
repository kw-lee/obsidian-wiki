import mimetypes
from pathlib import Path, PurePosixPath

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db.session import get_db
from app.services.git_ops import git_add_and_commit
from app.services.indexer import index_attachment_file
from app.services.sync_triggers import maybe_enqueue_sync_on_write
from app.services.vault import resolve

router = APIRouter()
MAX_ATTACHMENT_SIZE = 50 * 1024 * 1024
UPLOAD_CHUNK_SIZE = 1024 * 1024


def _invalid_upload(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _normalize_folder(folder: str) -> PurePosixPath:
    normalized = (folder or "attachments").strip().replace("\\", "/")
    if not normalized:
        normalized = "attachments"
    path = PurePosixPath(normalized)
    if path.is_absolute():
        raise _invalid_upload("Folder must be relative")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise _invalid_upload("Folder contains unsafe path segments")
    if any(":" in part for part in path.parts):
        raise _invalid_upload("Folder contains unsafe path segments")
    if any(part.startswith(".") for part in path.parts):
        raise _invalid_upload("Folder cannot target hidden directories")
    return path


def _normalize_filename(filename: str) -> str:
    normalized = filename.strip().replace("\\", "/")
    if not normalized:
        raise _invalid_upload("No filename")
    if "/" in normalized or ":" in normalized:
        raise _invalid_upload("Filename contains unsafe path separators")
    if normalized in {".", ".."} or normalized.startswith("."):
        raise _invalid_upload("Filename cannot target hidden files")
    return normalized


async def _write_upload(full: Path, file: UploadFile) -> int:
    total = 0
    temp = full.parent / f".{full.name}.uploading"
    try:
        async with aiofiles.open(temp, "wb") as handle:
            while True:
                chunk = await file.read(UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_ATTACHMENT_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"File too large. Max {MAX_ATTACHMENT_SIZE} bytes",
                    )
                await handle.write(chunk)
        temp.replace(full)
    finally:
        temp.unlink(missing_ok=True)
    return total


@router.get("/{path:path}")
async def get_attachment(
    path: str,
    _user: str = Depends(get_current_user),
) -> FileResponse:
    full = resolve(path)
    if not full.exists() or full.is_dir():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    mime = mimetypes.guess_type(str(full))[0] or "application/octet-stream"
    return FileResponse(full, media_type=mime)


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    file: UploadFile,
    request: Request,
    folder: str = "attachments",
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
) -> dict:
    if not file.filename:
        raise _invalid_upload("No filename")

    folder_path = _normalize_folder(folder)
    filename = _normalize_filename(file.filename)
    relative = (folder_path / filename).as_posix()

    try:
        full = resolve(relative)
    except ValueError as exc:
        raise _invalid_upload("Upload destination is outside the vault") from exc

    full.parent.mkdir(parents=True, exist_ok=True)
    size = await _write_upload(full, file)

    git_add_and_commit([relative], f"web: upload {relative}")
    await index_attachment_file(db, relative, full)
    await db.commit()
    await maybe_enqueue_sync_on_write(request, db)

    return {"path": relative, "size": size}
