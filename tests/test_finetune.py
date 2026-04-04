"""Tests for fine-tuning export"""
import pytest
import tempfile
import json
import os
from pathlib import Path
from cortex.knowledgebase import KnowledgeBase
from cortex.finetune import FineTuneExporter


@pytest.fixture
def temp_wiki():
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_path = Path(tmpdir) / "wiki"
        raw_path = Path(tmpdir) / "raw"
        kb = KnowledgeBase(str(wiki_path), str(raw_path))
        
        # Create a substantial article for testing
        kb.write_article("concepts/ml.md", """# Machine Learning

Machine learning is a subset of artificial intelligence.

## Supervised Learning

Supervised learning uses labeled training data to learn a mapping from inputs to outputs. The model is trained on examples where the correct answer is known, and it learns to predict the answer for new, unseen data.

Common algorithms include linear regression, logistic regression, decision trees, random forests, and support vector machines.

## Unsupervised Learning

Unsupervised learning finds hidden patterns in unlabeled data. The algorithm must discover structure on its own.

Clustering and dimensionality reduction are the main types.

## Reinforcement Learning

Reinforcement learning trains agents through rewards and penalties. The agent learns to take actions that maximize cumulative reward over time.
""")
        
        yield kb


def test_export_qa_dataset(temp_wiki):
    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, "qa.jsonl")
        exporter = FineTuneExporter(temp_wiki)
        path = exporter.export_qa_dataset(output, num_questions=10)
        
        assert os.path.exists(path)
        
        with open(path) as f:
            lines = f.readlines()
        
        assert len(lines) > 0
        
        # Verify format
        sample = json.loads(lines[0])
        assert "messages" in sample
        assert len(sample["messages"]) == 3
        assert sample["messages"][0]["role"] == "system"
        assert sample["messages"][1]["role"] == "user"
        assert sample["messages"][2]["role"] == "assistant"


def test_export_instruction_dataset(temp_wiki):
    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, "instruction.jsonl")
        exporter = FineTuneExporter(temp_wiki)
        path = exporter.export_instruction_dataset(output, num_instructions=10)
        
        assert os.path.exists(path)
        
        with open(path) as f:
            lines = f.readlines()
        
        assert len(lines) > 0
        
        sample = json.loads(lines[0])
        assert "messages" in sample


def test_export_completion_dataset(temp_wiki):
    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, "completion.jsonl")
        exporter = FineTuneExporter(temp_wiki)
        path = exporter.export_completion_dataset(output, num_samples=10)
        
        assert os.path.exists(path)
        
        with open(path) as f:
            lines = f.readlines()
        
        assert len(lines) > 0
        
        sample = json.loads(lines[0])
        assert "prompt" in sample
        assert "completion" in sample


def test_empty_wiki_produces_empty_dataset():
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_path = Path(tmpdir) / "wiki"
        raw_path = Path(tmpdir) / "raw"
        kb = KnowledgeBase(str(wiki_path), str(raw_path))
        
        output = os.path.join(tmpdir, "qa.jsonl")
        exporter = FineTuneExporter(kb)
        path = exporter.export_qa_dataset(output, num_questions=10)
        
        assert os.path.exists(path)
        
        with open(path) as f:
            content = f.read().strip()
        
        assert content == ""
