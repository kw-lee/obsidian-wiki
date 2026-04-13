import pytest

from app.services.tasks import extract_tasks_from_content
from app.services.vault import write_doc


def test_extract_tasks_from_content_parses_due_dates_and_priority():
    tasks = extract_tasks_from_content(
        "notes/todo.md",
        """
- [ ] Ship release 📅 2026-04-20 ⏫
- [x] Archive notes
""".strip(),
    )

    assert len(tasks) == 2
    assert tasks[0].text == "Ship release"
    assert tasks[0].completed is False
    assert tasks[0].due_date is not None
    assert tasks[0].priority == "high"
    assert tasks[1].completed is True


@pytest.mark.asyncio
async def test_get_tasks_filters_completed_by_default(client, auth_headers, setup_vault):
    await write_doc(
        "todo.md",
        """
- [ ] Draft proposal 📅 2026-04-18
- [x] Ship patch
""".strip(),
    )

    resp = await client.get("/api/tasks", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["text"] == "Draft proposal"
    assert data["tasks"][0]["completed"] is False


@pytest.mark.asyncio
async def test_get_tasks_can_include_completed(client, auth_headers, setup_vault):
    await write_doc(
        "team/weekly.md",
        """
- [x] Review notes
- [ ] Prepare retro
""".strip(),
    )

    resp = await client.get("/api/tasks?include_done=true", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert [task["text"] for task in data["tasks"]] == ["Prepare retro", "Review notes"]


@pytest.mark.asyncio
async def test_tasks_requires_auth(client, setup_vault):
    resp = await client.get("/api/tasks")
    assert resp.status_code in (401, 403)
