from app.services.conflict import three_way_merge


def test_no_change():
    base = "line1\nline2\nline3\n"
    merged, diff = three_way_merge(base, base, base)
    assert merged == base
    assert diff is None


def test_only_ours_changed():
    base = "line1\nline2\nline3\n"
    ours = "line1\nmodified\nline3\n"
    merged, diff = three_way_merge(base, ours, base)
    assert merged == ours
    assert diff is None


def test_only_theirs_changed():
    base = "line1\nline2\nline3\n"
    theirs = "line1\nline2\nmodified\n"
    merged, diff = three_way_merge(base, base, theirs)
    assert merged == theirs
    assert diff is None


def test_non_overlapping_merge():
    base = "line1\nline2\nline3\nline4\n"
    ours = "modified1\nline2\nline3\nline4\n"
    theirs = "line1\nline2\nline3\nmodified4\n"
    merged, diff = three_way_merge(base, ours, theirs)
    assert merged is not None
    assert "modified1" in merged
    assert "modified4" in merged
    assert diff is None


def test_overlapping_conflict():
    base = "line1\nline2\nline3\n"
    ours = "line1\nours_modified\nline3\n"
    theirs = "line1\ntheirs_modified\nline3\n"
    merged, diff = three_way_merge(base, ours, theirs)
    assert merged is None
    assert diff is not None
