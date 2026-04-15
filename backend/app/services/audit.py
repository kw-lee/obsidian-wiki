from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.db.models import AuditLog


async def record_audit_log(
    db: AsyncSession,
    *,
    user: CurrentUser,
    action: str,
    path: str,
    commit_sha: str | None,
) -> None:
    db.add(
        AuditLog(
            user_id=user.id,
            username=user.username,
            git_display_name=user.git_display_name,
            git_email=user.git_email,
            action=action,
            path=path,
            commit_sha=commit_sha,
        )
    )
