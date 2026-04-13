"""3-way merge conflict detection and resolution."""

import difflib
from dataclasses import dataclass


def three_way_merge(base: str, ours: str, theirs: str) -> tuple[str | None, str | None]:
    """
    Attempt a 3-way merge.
    Returns (merged_content, None) on success, or (None, diff_text) on conflict.
    """
    base_lines = base.splitlines(keepends=True)
    ours_lines = ours.splitlines(keepends=True)
    theirs_lines = theirs.splitlines(keepends=True)

    # If only one side changed, take that side
    if base_lines == ours_lines:
        return theirs, None
    if base_lines == theirs_lines:
        return ours, None

    # Both changed — check if changes overlap
    ours_changed = _changed_line_numbers(base_lines, ours_lines)
    theirs_changed = _changed_line_numbers(base_lines, theirs_lines)

    if not ours_changed.intersection(theirs_changed):
        # Non-overlapping: apply theirs on top of ours
        merged = ours_lines[:]
        theirs_ops = list(difflib.SequenceMatcher(None, base_lines, theirs_lines).get_opcodes())
        offset = 0
        for tag, i1, i2, j1, j2 in theirs_ops:
            if tag == "equal":
                continue
            merged[i1 + offset : i2 + offset] = theirs_lines[j1:j2]
            offset += (j2 - j1) - (i2 - i1)
        return "".join(merged), None

    # Overlapping changes → conflict
    diff_text = "".join(
        difflib.unified_diff(ours_lines, theirs_lines, fromfile="yours", tofile="theirs")
    )
    return None, diff_text


def _changed_line_numbers(base: list[str], modified: list[str]) -> set[int]:
    """Return set of line numbers in base that were changed."""
    matcher = difflib.SequenceMatcher(None, base, modified)
    changed = set()
    for tag, i1, i2, _j1, _j2 in matcher.get_opcodes():
        if tag != "equal":
            changed.update(range(i1, i2))
    return changed


@dataclass(frozen=True)
class MergeResult:
    merged_content: bytes | None
    diff: str | None


def merge_text_bytes(base: str | None, ours: bytes, theirs: bytes) -> MergeResult:
    """Attempt a UTF-8 text merge using a stored base snapshot.

    Returns a merged byte string when all inputs are valid UTF-8 text and the
    merge succeeds. If contents are binary/undecodable or the edits overlap, the
    diff field contains a best-effort explanation.
    """
    if base is None:
        return MergeResult(None, "No base content available for automatic merge")

    try:
        ours_text = ours.decode("utf-8")
        theirs_text = theirs.decode("utf-8")
    except UnicodeDecodeError:
        return MergeResult(None, "Automatic merge is only supported for UTF-8 text files")

    merged, diff = three_way_merge(base, ours_text, theirs_text)
    if merged is None:
        return MergeResult(None, diff)
    return MergeResult(merged.encode("utf-8"), None)
