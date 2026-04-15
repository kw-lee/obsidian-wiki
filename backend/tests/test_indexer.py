from datetime import date

import pytest
from sqlalchemy import select

from app.db.models import Attachment
from app.services.indexer import (
    _extract_links,
    _extract_tags,
    _resolve_title,
    _serialize_frontmatter,
    full_reindex,
    incremental_reindex,
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


@pytest.mark.asyncio
async def test_full_reindex_indexes_attachment_metadata(client, setup_vault):
    from app.db.session import async_session

    (setup_vault / "notes").mkdir()
    (setup_vault / "assets").mkdir()
    (setup_vault / "notes" / "entry.md").write_text("# Entry\n", encoding="utf-8")
    (setup_vault / "assets" / "diagram.png").write_bytes(b"png-data")

    async with async_session() as session:
        count = await full_reindex(session)
        assert count == 1

        result = await session.execute(
            select(Attachment).where(Attachment.path == "assets/diagram.png")
        )
        attachment = result.scalar_one()

    assert attachment.mime_type == "image/png"
    assert attachment.size_bytes == len(b"png-data")


@pytest.mark.asyncio
async def test_incremental_reindex_updates_attachment_metadata_and_deletes_removed_rows(
    client, setup_vault
):
    from app.db.session import async_session

    (setup_vault / "assets").mkdir()
    attachment_path = setup_vault / "assets" / "clip.mp3"
    attachment_path.write_bytes(b"v1")

    async with async_session() as session:
        await full_reindex(session)

    attachment_path.write_bytes(b"version-two")
    async with async_session() as session:
        await incremental_reindex(session, ["assets/clip.mp3"])
        result = await session.execute(
            select(Attachment).where(Attachment.path == "assets/clip.mp3")
        )
        attachment = result.scalar_one()

    assert attachment.mime_type == "audio/mpeg"
    assert attachment.size_bytes == len(b"version-two")

    attachment_path.unlink()
    async with async_session() as session:
        await incremental_reindex(session, ["assets/clip.mp3"])
        result = await session.execute(
            select(Attachment).where(Attachment.path == "assets/clip.mp3")
        )
        assert result.scalar_one_or_none() is None
