"""Integration test for full KB workflow"""
import pytest
import tempfile
import json
import os
from cortex import (
    KnowledgeBase, OutputRenderer, WikiHealthChecker,
    FineTuneExporter, Memory,
)


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_path = os.path.join(tmpdir, "wiki")
        raw_path = os.path.join(tmpdir, "raw")
        outputs_path = os.path.join(tmpdir, "outputs")
        memory = Memory()
        kb = KnowledgeBase(wiki_path, raw_path, memory=memory)
        yield kb, wiki_path, raw_path, outputs_path


def test_full_kb_workflow(temp_workspace):
    kb, wiki_path, raw_path, outputs_path = temp_workspace
    
    # Step 1: Create articles
    kb.write_article("concepts/ml.md", """# Machine Learning

Machine learning is a subset of AI.

## Supervised Learning

Uses labeled data to train models. Common algorithms include linear regression and decision trees.

## Unsupervised Learning

Finds patterns in unlabeled data. Clustering and dimensionality reduction are main types.
""")
    
    kb.write_article("concepts/dl.md", """# Deep Learning

Deep learning uses neural networks with multiple layers.

## CNNs

Great for image recognition.

## RNNs

Designed for sequential data.

## Related
See [Machine Learning](concepts/ml.md)
""")
    
    # Step 2: Build backlinks and index
    kb.update_backlinks()
    index = kb.generate_index()
    assert "Machine Learning" in index
    assert "Deep Learning" in index
    
    # Step 3: Verify backlinks
    backlinks = kb.get_backlinks("concepts/ml.md")
    assert "concepts/dl.md" in backlinks
    
    # Step 4: Search
    results = kb.search("neural networks layers")
    assert len(results) > 0
    
    # Step 5: Health check
    checker = WikiHealthChecker(kb)
    issues = checker.check_all()
    assert isinstance(issues, list)
    
    summary = checker.get_summary()
    assert "total_issues" in summary
    assert "by_severity" in summary
    
    # Step 6: Render output
    renderer = OutputRenderer(outputs_path)
    article = kb.get_article("concepts/dl.md")
    slides_path = renderer.render_marp(article.content)
    assert os.path.exists(slides_path)
    assert "<html>" in open(slides_path).read().lower()
    
    # Step 7: Fine-tuning export
    exporter = FineTuneExporter(kb)
    qa_path = exporter.export_qa_dataset(os.path.join(outputs_path, "qa.jsonl"), num_questions=10)
    assert os.path.exists(qa_path)
    
    with open(qa_path) as f:
        lines = f.readlines()
    assert len(lines) > 0
    
    sample = json.loads(lines[0])
    assert "messages" in sample
    assert len(sample["messages"]) == 3


def test_empty_kb_handles_gracefully(temp_workspace):
    kb, wiki_path, raw_path, outputs_path = temp_workspace
    
    # Search on empty wiki should not crash
    results = kb.search("anything")
    assert isinstance(results, list)
    
    # Health check on empty wiki should not crash
    checker = WikiHealthChecker(kb)
    issues = checker.check_all()
    assert isinstance(issues, list)
    
    # Index generation should work
    index = kb.generate_index()
    assert "Knowledge Base Index" in index


def test_stats_accuracy(temp_workspace):
    kb, wiki_path, raw_path, outputs_path = temp_workspace
    
    kb.write_article("test.md", "# Test\n\nOne two three four five")
    
    stats = kb.get_stats()
    assert stats["total_articles"] >= 1
    assert stats["total_words"] > 0
    assert stats["backlink_count"] == 0
