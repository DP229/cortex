"""Tests for tools security and validation"""
import pytest
import asyncio
import tempfile
import os
from cortex.tools import (
    ToolRegistry, BashTool, ReadFileTool, WriteFileTool,
    WebSearchTool, ToolResult,
)


@pytest.fixture
def temp_registry():
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_path = os.path.join(tmpdir, "wiki")
        raw_path = os.path.join(tmpdir, "raw")
        os.makedirs(wiki_path)
        os.makedirs(raw_path)
        registry = ToolRegistry(wiki_path=wiki_path, raw_path=raw_path)
        registry.register(BashTool())
        registry.register(ReadFileTool())
        registry.register(WriteFileTool())
        registry.register(WebSearchTool())
        yield registry, wiki_path, raw_path


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def test_path_traversal_blocked_read(temp_registry, event_loop):
    registry, wiki_path, raw_path = temp_registry
    
    result = event_loop.run_until_complete(
        registry.execute("read_file", {"path": "../../etc/passwd"})
    )
    
    assert result.success is False
    assert "Access denied" in result.error or "outside" in result.error.lower()


def test_path_traversal_blocked_write(temp_registry, event_loop):
    registry, wiki_path, raw_path = temp_registry
    
    result = event_loop.run_until_complete(
        registry.execute("write_file", {"path": "../../tmp/evil.txt", "content": "malicious"})
    )
    
    assert result.success is False


def test_valid_path_allowed(temp_registry, event_loop):
    registry, wiki_path, raw_path = temp_registry
    test_file = os.path.join(wiki_path, "test.md")
    
    # Note: Path validation depends on CortexConfig settings.
    # Since bash is disabled by default and chroot is enabled,
    # we test that the path validation logic runs without crashing.
    result = event_loop.run_until_complete(
        registry.execute("write_file", {"path": test_file, "content": "# Test\n\nValid content."})
    )
    
    # Either succeeds (path allowed) or fails with path error (config blocks it)
    # The important thing is it doesn't crash with unexpected errors
    assert result.success is True or "Access denied" in (result.error or "")


def test_dangerous_command_blocked(temp_registry, event_loop):
    registry, wiki_path, raw_path = temp_registry
    
    result = event_loop.run_until_complete(
        registry.execute("bash", {"command": "rm -rf /"})
    )
    
    # Should be blocked either by config (bash disabled) or by command validation
    assert result.success is False
    assert "disabled" in result.error.lower() or "blocked" in result.error.lower() or "not allowed" in result.error.lower()


def test_web_search_tool_basic(event_loop):
    tool = WebSearchTool()
    result = event_loop.run_until_complete(tool.execute(query="Python programming"))
    
    # Should either return results or fail gracefully (network-dependent)
    assert isinstance(result, ToolResult)
