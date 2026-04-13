"""Git operations for vault synchronization."""

import logging
from pathlib import Path

from git import GitCommandError, InvalidGitRepositoryError, Repo

from app.config import settings

logger = logging.getLogger(__name__)


def get_repo(*, git_remote_url: str = "") -> Repo:
    vp = Path(settings.vault_local_path)
    try:
        repo = Repo(vp)
    except InvalidGitRepositoryError:
        logger.info("Initializing git repo at %s", vp)
        repo = Repo.init(vp)
    if git_remote_url:
        if "origin" not in [r.name for r in repo.remotes]:
            repo.create_remote("origin", git_remote_url)
        elif repo.remotes.origin.url != git_remote_url:
            repo.remotes.origin.set_url(git_remote_url)
    return repo


def head_commit_sha(*, git_remote_url: str = "") -> str | None:
    repo = get_repo(git_remote_url=git_remote_url)
    if repo.head.is_valid():
        return repo.head.commit.hexsha
    return None


def changed_files_since(old_sha: str, new_sha: str, *, git_remote_url: str = "") -> list[str]:
    """Return list of file paths changed between two commits."""
    repo = get_repo(git_remote_url=git_remote_url)
    diff = repo.commit(old_sha).diff(repo.commit(new_sha))
    return [d.a_path or d.b_path for d in diff]


def file_changed_between(
    path: str, old_sha: str, new_sha: str, *, git_remote_url: str = ""
) -> bool:
    return path in changed_files_since(old_sha, new_sha, git_remote_url=git_remote_url)


def git_add_and_commit(paths: list[str], message: str, *, git_remote_url: str = "") -> str | None:
    """Stage files and commit. Returns new commit sha or None if nothing to commit."""
    repo = get_repo(git_remote_url=git_remote_url)
    repo.index.add(paths)
    if not repo.index.diff("HEAD") and not repo.untracked_files:
        return None
    commit = repo.index.commit(message)
    return commit.hexsha


def git_pull(*, git_remote_url: str = "", git_branch: str = "main") -> tuple[str | None, list[str]]:
    """Pull from remote. Returns (new_head_sha, changed_files)."""
    repo = get_repo(git_remote_url=git_remote_url)
    if "origin" not in [r.name for r in repo.remotes]:
        return head_commit_sha(git_remote_url=git_remote_url), []
    old_sha = head_commit_sha(git_remote_url=git_remote_url)
    try:
        origin = repo.remotes.origin
        origin.fetch()
        remote_branch = f"origin/{git_branch}"
        if old_sha is None:
            origin.pull(git_branch)
        else:
            repo.git.rebase(remote_branch)
    except GitCommandError as e:
        logger.error("Git pull failed: %s", e)
        try:
            repo.git.rebase("--abort")
        except GitCommandError:
            logger.debug("No rebase in progress to abort")
        raise
    new_sha = head_commit_sha(git_remote_url=git_remote_url)
    has_changes = old_sha and new_sha and old_sha != new_sha
    files = changed_files_since(old_sha, new_sha, git_remote_url=git_remote_url) if has_changes else []
    return new_sha, files


def git_push(*, git_remote_url: str = "", git_branch: str = "main") -> None:
    repo = get_repo(git_remote_url=git_remote_url)
    if "origin" not in [r.name for r in repo.remotes]:
        return
    repo.remotes.origin.push(git_branch)


def sync_status(*, git_remote_url: str = "", git_branch: str = "main") -> dict:
    repo = get_repo(git_remote_url=git_remote_url)
    result = {
        "backend": "git",
        "head": head_commit_sha(git_remote_url=git_remote_url),
        "last_sync": None,
        "ahead": 0,
        "behind": 0,
        "dirty": repo.is_dirty(),
        "message": None,
    }
    if "origin" not in [r.name for r in repo.remotes]:
        result["message"] = "Git remote is not configured"
        return result
    try:
        repo.remotes.origin.fetch()
        local = repo.head.commit
        remote_branch = f"origin/{git_branch}"
        ahead = len(list(repo.iter_commits(f"{remote_branch}..HEAD")))
        behind = len(list(repo.iter_commits(f"HEAD..{remote_branch}")))
        result["ahead"] = ahead
        result["behind"] = behind
        result["last_sync"] = local.committed_datetime.isoformat()
    except Exception:
        result["message"] = "Unable to fetch remote sync status"
    return result
