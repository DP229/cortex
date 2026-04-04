"""
Example: Knowledge Base Workflow

Demonstrates the full Cortex workflow:
1. Initialize a knowledge base
2. Ingest documents
3. Ask questions
4. Maintain the wiki
5. Export for fine-tuning

Run:
    python examples/kb_workflow.py
"""

import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cortex import (
    KnowledgeBase,
    IngestPipeline,
    QueryAgent,
    WikiCompiler,
    OutputRenderer,
    WikiHealthChecker,
    FineTuneExporter,
    create_kb_agent,
    Memory,
)


def main():
    print("=" * 60)
    print("Cortex — Knowledge Base Workflow Example")
    print("=" * 60)

    # Create a temporary workspace
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_path = os.path.join(tmpdir, "wiki")
        raw_path = os.path.join(tmpdir, "raw")
        outputs_path = os.path.join(tmpdir, "outputs")

        # Step 1: Initialize
        print("\n📦 Step 1: Initialize knowledge base")
        memory = Memory()
        kb = KnowledgeBase(wiki_path, raw_path, memory=memory)
        stats = kb.get_stats()
        print(f"   Wiki: {wiki_path}")
        print(f"   Raw:  {raw_path}")
        print(f"   Stats: {stats}")

        # Step 2: Create some sample articles manually
        print("\n📝 Step 2: Create sample articles")
        
        kb.write_article("concepts/machine-learning.md", """# Machine Learning

Machine learning is a subset of artificial intelligence that focuses on building systems that learn from data.

## Key Concepts

### Supervised Learning
Learning from labeled examples to make predictions.

### Unsupervised Learning
Finding patterns in unlabeled data.

### Reinforcement Learning
Learning through trial and error with rewards.

## Related
See also: [Deep Learning](concepts/deep-learning.md)
""")

        kb.write_article("concepts/deep-learning.md", """# Deep Learning

Deep learning uses neural networks with multiple layers to learn hierarchical representations.

## Architectures

### Convolutional Neural Networks (CNNs)
Great for image recognition and computer vision.

### Recurrent Neural Networks (RNNs)
Designed for sequential data like text and time series.

### Transformers
Attention-based architecture that revolutionized NLP.

## Related
See also: [Machine Learning](concepts/machine-learning.md)
""")

        kb.write_article("concepts/transformers.md", """# Transformers

Transformers are a neural network architecture based on self-attention mechanisms.

## Key Innovation
The attention mechanism allows the model to weigh the importance of different parts of the input.

## Applications
- Natural language processing
- Computer vision
- Speech recognition

## Related
See also: [Deep Learning](concepts/deep-learning.md)
""")

        articles = kb.list_articles()
        print(f"   Created {len(articles)} articles")
        for a in articles:
            print(f"   - {a.path} ({a.word_count} words)")

        # Step 3: Update backlinks and index
        print("\n🔗 Step 3: Build backlinks and index")
        kb.update_backlinks()
        index = kb.generate_index()
        print(f"   Index generated ({len(index)} chars)")
        
        backlinks = kb.get_backlinks("concepts/deep-learning.md")
        print(f"   Backlinks to deep-learning.md: {backlinks}")

        # Step 4: Search
        print("\n🔍 Step 4: Search the wiki")
        results = kb.search("attention mechanism neural networks")
        print(f"   Found {len(results)} results")
        for article, score in results:
            print(f"   - {article.title} (score: {score:.2f})")

        # Step 5: Health check
        print("\n🏥 Step 5: Health check")
        checker = WikiHealthChecker(kb)
        issues = checker.check_all()
        summary = checker.get_summary()
        print(f"   Total issues: {summary['total_issues']}")
        print(f"   Errors: {summary['by_severity'].get('error', 0)}")
        print(f"   Warnings: {summary['by_severity'].get('warning', 0)}")
        
        suggestions = checker.suggest_new_articles()
        print(f"   Suggested articles: {suggestions[:5]}")

        # Step 6: Render output
        print("\n📊 Step 6: Render output")
        renderer = OutputRenderer(outputs_path)
        article = kb.get_article("concepts/transformers.md")
        slides_path = renderer.render_marp(article.content)
        print(f"   Slides: {slides_path}")

        # Step 7: Fine-tuning export
        print("\n🎯 Step 7: Export fine-tuning dataset")
        exporter = FineTuneExporter(kb)
        qa_path = exporter.export_qa_dataset(os.path.join(tmpdir, "qa.jsonl"), num_questions=10)
        print(f"   Dataset: {qa_path}")
        
        # Show first sample
        with open(qa_path) as f:
            first_line = f.readline()
            print(f"   First sample: {first_line[:100]}...")

        print("\n" + "=" * 60)
        print("✅ Workflow complete!")
        print("=" * 60)


if __name__ == "__main__":
    main()
