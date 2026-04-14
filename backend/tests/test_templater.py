import pytest

import app.db.session as session_mod
from app.services.indexer import index_file
from app.services.settings import ensure_app_settings
from app.services.vault import write_doc


async def _write_and_index_doc(path: str, content: str) -> None:
    await write_doc(path, content)
    async with session_mod.async_session() as session:
        await index_file(session, path, content)
        await session.commit()


@pytest.mark.asyncio
async def test_get_doc_returns_rendered_content_when_templater_enabled(
    client, auth_headers, setup_vault
):
    await _write_and_index_doc("templates/snippet.md", "Included alias: <% tp.frontmatter.alias %>")
    await _write_and_index_doc(
        "daily/2026-04-10.md",
        """---
alias: Demo Note
---
# <% tp.file.title %>
Next: <% tp.date.now("YYYY-MM-DD", 1, tp.file.title, "YYYY-MM-DD") %>
Folder: <% tp.file.folder(true) %>
Exists: <% tp.file.exists(tp.file.folder(true) + "/2026-04-10.md") %>
<% tp.file.include("[[../templates/snippet]]") %>
<%* if (true) { %>kept<%* } %>
""",
    )

    async with session_mod.async_session() as session:
        row = await ensure_app_settings(session)
        row.templater_enabled = True
        await session.commit()

    response = await client.get("/api/wiki/doc/daily/2026-04-10.md", headers=auth_headers)
    assert response.status_code == 200

    payload = response.json()
    assert payload["content"].startswith("---\nalias: Demo Note")
    assert payload["rendered_content"] is not None
    assert "# 2026-04-10" in payload["rendered_content"]
    assert "Next: 2026-04-11" in payload["rendered_content"]
    assert "Folder: daily" in payload["rendered_content"]
    assert "Exists: true" in payload["rendered_content"]
    assert "Included alias: Demo Note" in payload["rendered_content"]
    assert "<%* if (true) { %>kept<%* } %>" in payload["rendered_content"]


@pytest.mark.asyncio
async def test_get_doc_skips_rendered_content_when_templater_disabled(
    client, auth_headers, setup_vault
):
    await _write_and_index_doc("notes/demo.md", "# <% tp.file.title %>")

    async with session_mod.async_session() as session:
        row = await ensure_app_settings(session)
        row.templater_enabled = False
        await session.commit()

    response = await client.get("/api/wiki/doc/notes/demo.md", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["rendered_content"] is None
