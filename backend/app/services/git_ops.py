"""Git operations for vault synchronization."""

import logging
from pathlib import Path

from git import Actor, GitCommandError, InvalidGitRepositoryError, Repo

from app.config import settings

logger = logging.getLogger(__name__)
_DEFAULT_ACTOR = Actor("Obsidian Wiki", "noreply@obsidian-wiki.local")


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


def _vault_root() -> Path:
    return Path(settings.vault_local_path)


def _snapshot_vault_files() -> list[str]:
    vault = _vault_root()
    return sorted(
        str(path.relative_to(vault))
        for path in vault.rglob("*")
        if path.is_file() and ".git" not in path.parts
    )


def _ensure_local_branch(repo: Repo, git_branch: str) -> None:
    if repo.head.is_valid():
        repo.git.checkout("-B", git_branch)
        return
    repo.git.checkout("--orphan", git_branch)


def _has_remote_branch(repo: Repo, remote_branch: str) -> bool:
    return any(ref.name == remote_branch for ref in repo.references)


def _commit_index(repo: Repo, message: str) -> str:
    commit = repo.index.commit(message, author=_DEFAULT_ACTOR, committer=_DEFAULT_ACTOR)
    return commit.hexsha


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


def read_file_at_commit(path: str, commit_sha: str, *, git_remote_url: str = "") -> str:
    repo = get_repo(git_remote_url=git_remote_url)
    return repo.git.show(f"{commit_sha}:{path}")


def file_changed_between(
    path: str, old_sha: str, new_sha: str, *, git_remote_url: str = ""
) -> bool:
    return path in changed_files_since(old_sha, new_sha, git_remote_url=git_remote_url)


def git_add_and_commit(paths: list[str], message: str, *, git_remote_url: str = "") -> str | None:
    """Stage files and commit. Returns new commit sha or None if nothing to commit."""
    repo = get_repo(git_remote_url=git_remote_url)
    repo.index.add(paths)
    if repo.head.is_valid():
        if not repo.index.diff("HEAD") and not repo.untracked_files:
            return None
    elif not repo.index.entries and not repo.untracked_files:
        return None
    return _commit_index(repo, message)


def git_stage_move_and_commit(
    source_path: str,
    destination_path: str,
    message: str,
    *,
    git_remote_url: str = "",
) -> str | None:
    repo = get_repo(git_remote_url=git_remote_url)
    repo.git.add(destination_path)
    repo.git.rm("-r", "--cached", "--ignore-unmatch", source_path)
    if repo.head.is_valid():
        if not repo.index.diff("HEAD") and not repo.untracked_files:
            return None
    elif not repo.index.entries and not repo.untracked_files:
        return None
    return _commit_index(repo, message)


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
    files = (
        changed_files_since(old_sha, new_sha, git_remote_url=git_remote_url) if has_changes else []
    )
    return new_sha, files


def git_push(*, git_remote_url: str = "", git_branch: str = "main") -> None:
    repo = get_repo(git_remote_url=git_remote_url)
    if "origin" not in [r.name for r in repo.remotes]:
        return
    repo.remotes.origin.push(git_branch)


def git_bootstrap_from_remote(
    *,
    git_remote_url: str = "",
    git_branch: str = "main",
) -> tuple[str | None, list[str]]:
    repo = get_repo(git_remote_url=git_remote_url)
    if "origin" not in [r.name for r in repo.remotes]:
        raise ValueError("Git remote is not configured")

    before = set(_snapshot_vault_files())
    origin = repo.remotes.origin
    origin.fetch()
    remote_branch = f"origin/{git_branch}"
    if not _has_remote_branch(repo, remote_branch):
        raise ValueError(
            f"Remote branch '{git_branch}' does not exist yet. Use the local baseline first."
        )

    repo.git.clean("-fd")
    repo.git.checkout("-B", git_branch, remote_branch, force=True)
    repo.git.reset("--hard", remote_branch)
    repo.git.clean("-fd")

    after = set(_snapshot_vault_files())
    return head_commit_sha(git_remote_url=git_remote_url), sorted(before | after)


def git_bootstrap_from_local(
    *,
    git_remote_url: str = "",
    git_branch: str = "main",
) -> tuple[str | None, list[str]]:
    repo = get_repo(git_remote_url=git_remote_url)
    if "origin" not in [r.name for r in repo.remotes]:
        raise ValueError("Git remote is not configured")

    before = set(_snapshot_vault_files())
    _ensure_local_branch(repo, git_branch)
    repo.git.add(A=True)

    needs_commit = (
        not repo.head.is_valid()
        or repo.is_dirty(index=True, working_tree=True, untracked_files=True)
        or bool(repo.untracked_files)
    )
    if needs_commit:
        _commit_index(repo, "sync: bootstrap local baseline")

    origin = repo.remotes.origin
    repo.git.push("--force", "origin", f"{git_branch}:refs/heads/{git_branch}")
    origin.fetch(git_branch)
    repo.git.branch("--set-upstream-to", f"origin/{git_branch}", git_branch)

    after = set(_snapshot_vault_files())
    return head_commit_sha(git_remote_url=git_remote_url), sorted(before | after)


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
