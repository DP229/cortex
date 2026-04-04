"""Tests for ingest pipeline"""
import pytest
import tempfile
import os
import csv
import json
from pathlib import Path
from cortex.knowledgebase import KnowledgeBase
from cortex.ingest import IngestPipeline, IngestResult


@pytest.fixture
def temp_kb():
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_path = Path(tmpdir) / "wiki"
        raw_path = Path(tmpdir) / "raw"
        kb = KnowledgeBase(str(wiki_path), str(raw_path))
        yield kb


def test_ingest_text_file(temp_kb):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("# Test Article\n\nThis is test content for ingestion.")
        f.flush()
        path = f.name
    
    try:
        pipeline = IngestPipeline(temp_kb)
        result = pipeline.ingest_file(path)
        
        assert result.title == "Test Article"
        assert result.content_type == "text"
        assert result.word_count > 0
        assert "summaries/" in result.wiki_path
        
        article = temp_kb.get_article(result.wiki_path)
        assert article is not None
        assert "Test Article" in article.content
    finally:
        os.unlink(path)


def test_ingest_directory(temp_kb):
    with tempfile.TemporaryDirectory() as srcdir:
        Path(srcdir, "file1.md").write_text("# File 1\n\nContent one")
        Path(srcdir, "file2.txt").write_text("# File 2\n\nContent two")
        
        pipeline = IngestPipeline(temp_kb)
        results = pipeline.ingest_directory(srcdir, recursive=False)
        
        assert len(results) == 2
        assert all(isinstance(r, IngestResult) for r in results)


def test_ingest_code_file(temp_kb):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("def hello():\n    print('Hello, world!')\n")
        f.flush()
        path = f.name
    
    try:
        pipeline = IngestPipeline(temp_kb)
        result = pipeline.ingest_file(path)
        
        assert result.content_type == "code"
        assert result.title.endswith(".py")
        assert "```python" in temp_kb.get_article(result.wiki_path).content
    finally:
        os.unlink(path)


def test_ingest_json_file(temp_kb):
    data = {"name": "test", "version": "1.0", "description": "A test package"}
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(data, f)
        f.flush()
        path = f.name
    
    try:
        pipeline = IngestPipeline(temp_kb)
        result = pipeline.ingest_file(path)
        
        assert result.content_type == "data"
        article = temp_kb.get_article(result.wiki_path)
        assert article is not None
        assert "**name**" in article.content
    finally:
        os.unlink(path)


def test_ingest_csv_file(temp_kb):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["name", "age", "city"])
        writer.writerow(["Alice", "30", "NYC"])
        writer.writerow(["Bob", "25", "LA"])
        f.flush()
        path = f.name
    
    try:
        pipeline = IngestPipeline(temp_kb)
        result = pipeline.ingest_file(path)
        
        assert result.content_type == "data"
        article = temp_kb.get_article(result.wiki_path)
        assert article is not None
        assert "Rows: 2" in article.content
        assert "Columns: 3" in article.content
    finally:
        os.unlink(path)


def test_ingest_file_not_found(temp_kb):
    pipeline = IngestPipeline(temp_kb)
    
    with pytest.raises(FileNotFoundError):
        pipeline.ingest_file("/nonexistent/file.txt")


def test_ingest_image_file(temp_kb):
    png_header = bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
        0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
        0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
        0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0xFF,
        0x00, 0x05, 0xFE, 0x02, 0xFE, 0xA7, 0x9A, 0x9D,
        0x29, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,
        0x44, 0xAE, 0x42, 0x60, 0x82,
    ])
    
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.png', delete=False) as f:
        f.write(png_header)
        f.flush()
        path = f.name
    
    try:
        pipeline = IngestPipeline(temp_kb)
        result = pipeline.ingest_file(path)
        
        assert result.content_type == "image"
        image_path = temp_kb.raw_path / "images" / Path(path).name
        assert image_path.exists()
    finally:
        os.unlink(path)
