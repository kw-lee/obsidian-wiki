import mimetypes

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.auth import get_current_user
from app.services.git_ops import git_add_and_commit
from app.services.vault import resolve

router = APIRouter()


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
    folder: str = "attachments",
    _user: str = Depends(get_current_user),
) -> dict[str, str]:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No filename")

    relative = f"{folder}/{file.filename}"
    full = resolve(relative)
    full.parent.mkdir(parents=True, exist_ok=True)

    content = await file.read()
    full.write_bytes(content)

    git_add_and_commit([relative], f"web: upload {relative}")

    return {"path": relative, "size": len(content)}
