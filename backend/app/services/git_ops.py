"""Git operations for vault synchronization."""

import logging
from pathlib import Path

from git import GitCommandError, InvalidGitRepositoryError, Repo

from app.config import settings

logger = logging.getLogger(__name__)


def get_repo() -> Repo:
    vp = Path(settings.vault_local_path)
    try:
        return Repo(vp)
    except InvalidGitRepositoryError:
        logger.info("Initializing git repo at %s", vp)
        repo = Repo.init(vp)
        if settings.git_remote_url:
            repo.create_remote("origin", settings.git_remote_url)
        return repo


def head_commit_sha() -> str | None:
    repo = get_repo()
    if repo.head.is_valid():
        return repo.head.commit.hexsha
    return None


def changed_files_since(old_sha: str, new_sha: str) -> list[str]:
    """Return list of file paths changed between two commits."""
    repo = get_repo()
    diff = repo.commit(old_sha).diff(repo.commit(new_sha))
    return [d.a_path or d.b_path for d in diff]


def file_changed_between(path: str, old_sha: str, new_sha: str) -> bool:
    return path in changed_files_since(old_sha, new_sha)


def git_add_and_commit(paths: list[str], message: str) -> str | None:
    """Stage files and commit. Returns new commit sha or None if nothing to commit."""
    repo = get_repo()
    repo.index.add(paths)
    if not repo.index.diff("HEAD") and not repo.untracked_files:
        return None
    commit = repo.index.commit(message)
    return commit.hexsha


def git_pull() -> tuple[str | None, list[str]]:
    """Pull from remote. Returns (new_head_sha, changed_files)."""
    repo = get_repo()
    if "origin" not in [r.name for r in repo.remotes]:
        return head_commit_sha(), []
    old_sha = head_commit_sha()
    try:
        origin = repo.remotes.origin
        origin.fetch()
        remote_branch = f"origin/{settings.git_branch}"
        if old_sha is None:
            origin.pull(settings.git_branch)
        else:
            repo.git.rebase(remote_branch)
    except GitCommandError as e:
        logger.error("Git pull failed: %s", e)
        repo.git.rebase("--abort")
        raise
    new_sha = head_commit_sha()
    has_changes = old_sha and new_sha and old_sha != new_sha
    files = changed_files_since(old_sha, new_sha) if has_changes else []
    return new_sha, files


def git_push() -> None:
    repo = get_repo()
    if "origin" not in [r.name for r in repo.remotes]:
        return
    repo.remotes.origin.push(settings.git_branch)


def sync_status() -> dict:
    repo = get_repo()
    result = {"last_sync": None, "ahead": 0, "behind": 0, "dirty": repo.is_dirty()}
    if "origin" not in [r.name for r in repo.remotes]:
        return result
    try:
        repo.remotes.origin.fetch()
        local = repo.head.commit
        remote_branch = f"origin/{settings.git_branch}"
        ahead = len(list(repo.iter_commits(f"{remote_branch}..HEAD")))
        behind = len(list(repo.iter_commits(f"HEAD..{remote_branch}")))
        result["ahead"] = ahead
        result["behind"] = behind
        result["last_sync"] = local.committed_datetime.isoformat()
    except Exception:
        pass
    return result
