"""Tests for wiki tools"""
import pytest
import asyncio
import tempfile
from pathlib import Path
from cortex.knowledgebase import KnowledgeBase
from cortex.wiki_tools import (
    WikiReadTool, WikiWriteTool, WikiSearchTool,
    WikiIndexTool, WikiBacklinkTool, WikiListTool,
)


@pytest.fixture
def temp_kb():
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_path = Path(tmpdir) / "wiki"
        raw_path = Path(tmpdir) / "raw"
        kb = KnowledgeBase(str(wiki_path), str(raw_path))
        kb.write_article("concepts/test.md", "# Test\n\nTest content for wiki tools.")
        yield kb


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def test_wiki_read_tool(temp_kb, event_loop):
    tool = WikiReadTool(knowledgebase=temp_kb)
    result = event_loop.run_until_complete(tool.execute(path="concepts/test.md"))
    
    assert result.success is True
    assert "Test content" in result.output
    assert result.metadata["title"] == "Test"


def test_wiki_read_tool_not_found(temp_kb, event_loop):
    tool = WikiReadTool(knowledgebase=temp_kb)
    result = event_loop.run_until_complete(tool.execute(path="nonexistent.md"))
    
    assert result.success is False
    assert "not found" in result.error.lower()


def test_wiki_write_tool(temp_kb, event_loop):
    tool = WikiWriteTool(knowledgebase=temp_kb)
    result = event_loop.run_until_complete(
        tool.execute(path="concepts/new.md", content="# New Article\n\nNew content.")
    )
    
    assert result.success is True
    assert "new.md" in result.output
    assert result.metadata["word_count"] > 0


def test_wiki_search_tool(temp_kb, event_loop):
    tool = WikiSearchTool(knowledgebase=temp_kb)
    result = event_loop.run_until_complete(tool.execute(query="test content"))
    
    assert result.success is True
    assert "Test" in result.output


def test_wiki_index_tool(temp_kb, event_loop):
    tool = WikiIndexTool(knowledgebase=temp_kb)
    result = event_loop.run_until_complete(tool.execute())
    
    assert result.success is True
    assert "Knowledge Base Index" in result.output


def test_wiki_backlink_tool(temp_kb, event_loop):
    tool = WikiBacklinkTool(knowledgebase=temp_kb)
    result = event_loop.run_until_complete(tool.execute(path="concepts/test.md"))
    
    assert result.success is True


def test_wiki_list_tool(temp_kb, event_loop):
    tool = WikiListTool(knowledgebase=temp_kb)
    result = event_loop.run_until_complete(tool.execute())
    
    assert result.success is True
    assert "concepts/test.md" in result.output


def test_wiki_list_tool_by_category(temp_kb, event_loop):
    tool = WikiListTool(knowledgebase=temp_kb)
    result = event_loop.run_until_complete(tool.execute(category="concepts"))
    
    assert result.success is True
    assert "concepts" in result.output.lower()
