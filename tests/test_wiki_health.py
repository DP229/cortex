"""Tests for wiki health checker"""
import pytest
import tempfile
from pathlib import Path
from cortex.knowledgebase import KnowledgeBase
from cortex.wiki_health import WikiHealthChecker


@pytest.fixture
def temp_wiki():
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_path = Path(tmpdir) / "wiki"
        raw_path = Path(tmpdir) / "raw"
        yield KnowledgeBase(str(wiki_path), str(raw_path))


def test_broken_links(temp_wiki):
    temp_wiki.write_article("a.md", "# A\n\nSee [B](b.md)")
    temp_wiki.write_article("c.md", "# C\n\nContent")
    
    checker = WikiHealthChecker(temp_wiki)
    issues = checker.check_broken_links()
    
    broken = [i for i in issues if i.type == "broken_link"]
    assert len(broken) == 1
    assert broken[0].article == "a.md"
    assert "b.md" in broken[0].message


def test_orphaned_articles(temp_wiki):
    temp_wiki.write_article("a.md", "# A\n\nContent A")
    temp_wiki.write_article("b.md", "# B\n\nContent B")
    
    checker = WikiHealthChecker(temp_wiki)
    issues = checker.check_orphaned_articles()
    
    orphaned = [i for i in issues if i.type == "orphaned"]
    assert len(orphaned) == 2  # Both have no backlinks


def test_empty_articles(temp_wiki):
    temp_wiki.write_article("small.md", "# Small\n\nHi")
    temp_wiki.write_article("big.md", "# Big\n\n" + "word " * 100)
    
    checker = WikiHealthChecker(temp_wiki)
    issues = checker.check_empty_articles()
    
    empty = [i for i in issues if i.type == "empty"]
    assert len(empty) == 1
    assert empty[0].article == "small.md"


def test_no_broken_links_when_all_exist(temp_wiki):
    temp_wiki.write_article("a.md", "# A\n\nSee [B](b.md)")
    temp_wiki.write_article("b.md", "# B\n\nContent")
    
    checker = WikiHealthChecker(temp_wiki)
    issues = checker.check_broken_links()
    
    assert len(issues) == 0


def test_get_summary(temp_wiki):
    temp_wiki.write_article("a.md", "# A\n\nContent A")
    
    checker = WikiHealthChecker(temp_wiki)
    summary = checker.get_summary()
    
    assert "total_issues" in summary
    assert "by_severity" in summary
    assert "by_type" in summary
    assert "suggestions_count" in summary
