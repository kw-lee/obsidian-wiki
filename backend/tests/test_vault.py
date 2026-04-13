import pytest

from app.services.vault import (
    VaultPathPolicyError,
    build_tree,
    content_hash,
    delete_doc,
    read_doc,
    write_doc,
)


@pytest.mark.asyncio
async def test_write_and_read(setup_vault):
    h = await write_doc("test.md", "# Hello\nWorld")
    assert h == content_hash("# Hello\nWorld")

    content = await read_doc("test.md")
    assert content == "# Hello\nWorld"


@pytest.mark.asyncio
async def test_delete(setup_vault):
    await write_doc("to_delete.md", "content")
    await delete_doc("to_delete.md")
    with pytest.raises(FileNotFoundError):
        await read_doc("to_delete.md")


@pytest.mark.asyncio
async def test_nested_write(setup_vault):
    await write_doc("folder/sub/note.md", "nested content")
    content = await read_doc("folder/sub/note.md")
    assert content == "nested content"


def test_build_tree(setup_vault):
    vault = setup_vault
    (vault / "note1.md").write_text("# Note 1")
    sub = vault / "subfolder"
    sub.mkdir()
    (sub / "note2.md").write_text("# Note 2")

    tree = build_tree()
    names = {n["name"] for n in tree}
    assert "note1.md" in names
    assert "subfolder" in names


def test_path_traversal(setup_vault):
    from app.services.vault import resolve

    with pytest.raises(ValueError, match="Dot path segments are not allowed|Path traversal"):
        resolve("../../etc/passwd")


def test_resolve_rejects_git_paths(setup_vault):
    from app.services.vault import resolve

    with pytest.raises(VaultPathPolicyError, match=".git"):
        resolve(".git/config")


@pytest.mark.asyncio
async def test_write_rejects_obsidian_paths(setup_vault):
    with pytest.raises(VaultPathPolicyError, match=".obsidian"):
        await write_doc(".obsidian/workspace.json", "{}")
