from app.services.indexer import _extract_links, _extract_tags


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
