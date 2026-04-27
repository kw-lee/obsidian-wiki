import pytest

from scripts import bootstrap_alembic


class _FakeConnection:
    def __init__(self, version_num: str | None = None):
        self.version_num = version_num

    async def scalar(self, statement, params=None):  # noqa: ANN001
        del params
        sql = str(statement)
        if "SELECT version_num FROM alembic_version" in sql:
            return self.version_num
        return None


def _schema_probe(mapping: dict[str, bool]):
    async def fake_scalar_bool(conn, sql: str, **params):  # noqa: ANN001
        del conn, params
        for needle, value in sorted(mapping.items(), key=lambda item: len(item[0]), reverse=True):
            if needle in sql:
                return value
        return False

    return fake_scalar_bool


@pytest.mark.asyncio
async def test_detect_legacy_revision_handles_pre_katex_sync_schema(monkeypatch):
    conn = _FakeConnection()
    monkeypatch.setattr(
        bootstrap_alembic,
        "_scalar_bool",
        _schema_probe(
            {
                "table_name = 'alembic_version'": False,
                "table_name = 'app_settings'": True,
                "column_name = 'katex_enabled'": False,
                "column_name = 'dataview_show_source'": False,
                "table_name = 'audit_logs'": True,
                "column_name = 'git_email'": True,
            }
        ),
    )

    revision = await bootstrap_alembic.detect_legacy_revision(conn)

    assert revision == "20260415_0013"


@pytest.mark.asyncio
async def test_detect_legacy_revision_marks_head_when_katex_exists_and_edit_sessions_is_gone(
    monkeypatch,
):
    conn = _FakeConnection()
    monkeypatch.setattr(
        bootstrap_alembic,
        "_scalar_bool",
        _schema_probe(
            {
                "table_name = 'alembic_version'": False,
                "table_name = 'app_settings'": True,
                "column_name = 'katex_enabled'": True,
                "table_name = 'edit_sessions'": False,
            }
        ),
    )

    revision = await bootstrap_alembic.detect_legacy_revision(conn)

    assert revision == "20260415_0016"


@pytest.mark.asyncio
async def test_detect_legacy_revision_skips_bootstrap_when_alembic_version_is_present(monkeypatch):
    conn = _FakeConnection(version_num="20260415_0016")
    monkeypatch.setattr(
        bootstrap_alembic,
        "_scalar_bool",
        _schema_probe({"table_name = 'alembic_version'": True}),
    )

    revision = await bootstrap_alembic.detect_legacy_revision(conn)

    assert revision is None


@pytest.mark.asyncio
async def test_detect_legacy_revision_repairs_stale_alembic_version_when_schema_is_ahead(
    monkeypatch,
):
    conn = _FakeConnection(version_num="20260415_0011")
    monkeypatch.setattr(
        bootstrap_alembic,
        "_scalar_bool",
        _schema_probe(
            {
                "table_name = 'alembic_version'": True,
                "table_name = 'app_settings'": True,
                "column_name = 'katex_enabled'": False,
                "column_name = 'dataview_show_source'": False,
                "table_name = 'audit_logs'": True,
                "column_name = 'git_email'": True,
            }
        ),
    )

    revision = await bootstrap_alembic.detect_legacy_revision(conn)

    assert revision == "20260415_0013"
