"""Tests for KnowledgeBase"""
import pytest
import tempfile
from pathlib import Path
from cortex.knowledgebase import KnowledgeBase, Article


@pytest.fixture
def temp_wiki():
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_path = Path(tmpdir) / "wiki"
        raw_path = Path(tmpdir) / "raw"
        yield KnowledgeBase(str(wiki_path), str(raw_path))


def test_create_article(temp_wiki):
    article = temp_wiki.write_article("test.md", "# Test\n\nContent here")
    assert article.title == "Test"
    assert article.word_count > 0
    assert "Content here" in article.content


def test_read_article(temp_wiki):
    temp_wiki.write_article("test.md", "# Test\n\nContent here")
    article = temp_wiki.get_article("test.md")
    assert article is not None
    assert "Content here" in article.content


def test_delete_article(temp_wiki):
    temp_wiki.write_article("test.md", "# Test\n\nContent")
    assert temp_wiki.delete_article("test.md") is True
    assert temp_wiki.get_article("test.md") is None


def test_path_traversal_blocked(temp_wiki):
    result = temp_wiki.get_article("../../etc/passwd")
    assert result is None


def test_list_articles(temp_wiki):
    temp_wiki.write_article("concepts/a.md", "# A\n\nContent A")
    temp_wiki.write_article("concepts/b.md", "# B\n\nContent B")
    articles = temp_wiki.list_articles()
    assert len(articles) >= 2


def test_list_articles_by_category(temp_wiki):
    temp_wiki.write_article("concepts/a.md", "# A\n\nContent A")
    temp_wiki.write_article("summaries/b.md", "# B\n\nContent B")
    articles = temp_wiki.list_articles(category="concepts")
    assert all(a.category == "concepts" for a in articles)


def test_search_keyword(temp_wiki):
    temp_wiki.write_article("test.md", "# Machine Learning\n\nMachine learning is a subset of AI")
    results = temp_wiki.search("machine learning")
    assert len(results) > 0
    assert any("Machine Learning" in r[0].title for r in results)


def test_generate_index(temp_wiki):
    temp_wiki.write_article("concepts/a.md", "# A\n\nContent A")
    temp_wiki.write_article("concepts/b.md", "# B\n\nContent B")
    index = temp_wiki.generate_index()
    assert "A" in index
    assert "B" in index
    assert "concepts" in index.lower()


def test_backlinks(temp_wiki):
    temp_wiki.write_article("a.md", "# A\n\nSee [B](b.md)")
    temp_wiki.write_article("b.md", "# B\n\nContent B")
    temp_wiki.update_backlinks()
    backlinks = temp_wiki.get_backlinks("b.md")
    assert "a.md" in backlinks


def test_get_stats(temp_wiki):
    temp_wiki.write_article("test.md", "# Test\n\nContent with some words")
    stats = temp_wiki.get_stats()
    assert stats["total_articles"] >= 1
    assert stats["total_words"] > 0


def test_article_properties():
    article = Article(
        path="concepts/ml.md",
        title="Machine Learning",
        content="# Machine Learning\n\nContent",
        word_count=2,
    )
    assert article.filename == "ml.md"
    assert article.category == "concepts"
