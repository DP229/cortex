"""
Cortex Fine-Tuning - Generate datasets from wiki for model fine-tuning

Converts wiki content into fine-tuning datasets:
- Q&A pairs from article sections
- Text completion datasets
- Instruction-following datasets

Usage:
    exporter = FineTuneExporter(knowledgebase)
    exporter.export_qa_dataset("dataset.jsonl", num_questions=100)
"""

import json
import random
from pathlib import Path
import logging

from cortex.knowledgebase import KnowledgeBase

logger = logging.getLogger(__name__)


class FineTuneExporter:
    """Generate fine-tuning datasets from wiki content."""
    
    def __init__(self, knowledgebase: KnowledgeBase):
        self.kb = knowledgebase
    
    def export_qa_dataset(
        self,
        output_path: str,
        num_questions: int = 100,
    ) -> str:
        """
        Generate Q&A pairs from wiki articles.
        
        Format: OpenAI chat completions format
        """
        articles = self.kb.list_articles()
        qa_pairs = []
        
        for article in articles:
            if article.word_count < 20:
                continue
            
            # Generate questions from article sections
            sections = article.content.split("## ")
            
            for section in sections[1:]:  # Skip title
                lines = section.strip().split("\n")
                if not lines:
                    continue
                
                section_title = lines[0]
                section_content = "\n".join(lines[1:])
                
                if len(section_content.split()) < 10:
                    continue
                
                # Create Q&A pairs
                qa_pairs.append({
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant with deep knowledge of the topic."},
                        {"role": "user", "content": f"Explain: {section_title}"},
                        {"role": "assistant", "content": section_content.strip()},
                    ]
                })
                
                qa_pairs.append({
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": f"What is {section_title.lower()}?"},
                        {"role": "assistant", "content": section_content.strip()[:1000]},
                    ]
                })
        
        # Shuffle and limit
        random.shuffle(qa_pairs)
        qa_pairs = qa_pairs[:num_questions]
        
        # Write to JSONL
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, "w") as f:
            for pair in qa_pairs:
                f.write(json.dumps(pair) + "\n")
        
        return str(output_file)
    
    def export_completion_dataset(
        self,
        output_path: str,
        num_samples: int = 100,
    ) -> str:
        """Generate text completion dataset."""
        articles = self.kb.list_articles()
        samples = []
        
        for article in articles:
            if article.word_count < 20:
                continue
            
            # Split article into prompt/completion pairs
            words = article.content.split()
            mid = len(words) // 2
            
            samples.append({
                "prompt": " ".join(words[:mid]),
                "completion": " ".join(words[mid:]),
            })
        
        random.shuffle(samples)
        samples = samples[:num_samples]
        
        output_file = Path(output_path)
        with open(output_file, "w") as f:
            for sample in samples:
                f.write(json.dumps(sample) + "\n")
        
        return str(output_file)
    
    def export_instruction_dataset(
        self,
        output_path: str,
        num_instructions: int = 100,
    ) -> str:
        """Generate instruction-following dataset."""
        articles = self.kb.list_articles()
        instructions = []
        
        for article in articles:
            if article.word_count < 100:
                continue
            
            instructions.append({
                "messages": [
                    {"role": "system", "content": "You are a knowledgeable assistant."},
                    {"role": "user", "content": f"Write a comprehensive article about {article.title}"},
                    {"role": "assistant", "content": article.content},
                ]
            })
            
            instructions.append({
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": f"Summarize the key points about {article.title}"},
                    {"role": "assistant", "content": article.content[:1000]},
                ]
            })
        
        random.shuffle(instructions)
        instructions = instructions[:num_instructions]
        
        output_file = Path(output_path)
        with open(output_file, "w") as f:
            for inst in instructions:
                f.write(json.dumps(inst) + "\n")
        
        return str(output_file)
