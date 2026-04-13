from datetime import date

from app.services.indexer import (
    _extract_links,
    _extract_tags,
    _resolve_title,
    _serialize_frontmatter,
)


def test_extract_wikilinks():
    content = "See [[OtherNote]] and [[folder/page|alias text]]."
    links = _extract_links(content)
    assert ("OtherNote", None) in links
    assert ("folder/page", "alias text") in links


def test_extract_wikilinks_empty():
    assert _extract_links("No links here") == []


def test_extract_tags_inline():
    content = "Some text #python and #한글tag here"
    tags = _extract_tags(content, [])
    assert "python" in tags
    assert "한글tag" in tags


def test_extract_tags_frontmatter():
    tags = _extract_tags("body text", ["fm-tag1", "fm-tag2"])
    assert "fm-tag1" in tags
    assert "fm-tag2" in tags


def test_extract_tags_combined():
    content = "Some #inline text"
    tags = _extract_tags(content, ["frontmatter"])
    assert "inline" in tags
    assert "frontmatter" in tags


def test_extract_tags_dedup():
    content = "#dup some text #dup"
    tags = _extract_tags(content, ["dup"])
    assert tags.count("dup") == 1


def test_extract_tags_no_false_positives():
    content = "email@test.com and http://example.com/#fragment"
    tags = _extract_tags(content, [])
    assert "test.com" not in tags


def test_extract_tags_handles_null_frontmatter():
    tags = _extract_tags("body text", None)
    assert tags == []


def test_extract_tags_handles_mixed_frontmatter_values():
    tags = _extract_tags("body text", ["alpha", None, " beta ", 3])
    assert tags == ["3", "alpha", "beta"]


def test_serialize_frontmatter_converts_date_values_to_json_safe_strings():
    serialized = _serialize_frontmatter(
        {
            "release_date": date(2026, 4, 13),
            "nested": {"start": date(2026, 4, 14)},
            "tags": {"alpha", "beta"},
        }
    )

    assert serialized["release_date"] == "2026-04-13"
    assert serialized["nested"]["start"] == "2026-04-14"
    assert sorted(serialized["tags"]) == ["alpha", "beta"]


def test_resolve_title_falls_back_when_frontmatter_title_is_null():
    assert _resolve_title("templates/seminar.md", {"title": None}) == "seminar"


def test_resolve_title_falls_back_when_frontmatter_title_is_blank():
    assert _resolve_title("templates/seminar.md", {"title": "   "}) == "seminar"


def test_resolve_title_stringifies_non_string_frontmatter_titles():
    assert _resolve_title("templates/seminar.md", {"title": 2026}) == "2026"
