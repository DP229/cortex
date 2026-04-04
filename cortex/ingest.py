"""
Cortex Ingest Pipeline - Data ingestion for knowledge base

Supports:
- PDF documents → markdown
- Web articles → readable markdown
- Code repositories → structured markdown
- Images → extracted and referenced
- CSV/JSON/YAML → summary markdown
- Plain text → markdown

Usage:
    pipeline = IngestPipeline(knowledgebase)
    result = pipeline.ingest_file("path/to/document.pdf")
    results = pipeline.ingest_directory("path/to/folder/")
"""

import re
import json
import time
from pathlib import Path
from typing import List
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    """Result of ingesting a file"""
    source_path: str
    wiki_path: str
    title: str
    word_count: int
    content_type: str  # "pdf", "web", "code", "image", "data"
    summary: str = ""
    concepts: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


class IngestPipeline:
    """
    Pipeline for ingesting various document types into the knowledge base.
    """
    
    def __init__(self, knowledgebase, llm_client=None):
        self.kb = knowledgebase
        self.llm = llm_client  # Brain instance for LLM-powered extraction
    
    def ingest_file(self, path: str) -> IngestResult:
        """Ingest a single file, auto-detecting format"""
        source = Path(path).resolve()
        if not source.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        ext = source.suffix.lower()
        
        if ext == ".pdf":
            return self._ingest_pdf(source)
        elif ext in (".md", ".txt"):
            return self._ingest_text(source)
        elif ext in (".html", ".htm"):
            return self._ingest_html(source)
        elif ext in (".py", ".js", ".ts", ".go", ".rs", ".java", ".c", ".cpp", ".h"):
            return self._ingest_code(source)
        elif ext in (".json", ".yaml", ".yml", ".csv"):
            return self._ingest_data(source)
        elif ext in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"):
            return self._ingest_image(source)
        else:
            return self._ingest_generic(source)
    
    def ingest_directory(self, path: str, recursive: bool = True) -> List[IngestResult]:
        """Ingest all files in a directory"""
        source = Path(path).resolve()
        results = []
        
        pattern = "**/*" if recursive else "*"
        for file_path in source.glob(pattern):
            if file_path.is_file():
                try:
                    result = self.ingest_file(str(file_path))
                    results.append(result)
                except Exception as e:
                    logger.error(f"Failed to ingest {file_path}: {e}")
        
        return results
    
    def ingest_web_url(self, url: str) -> IngestResult:
        """Ingest a web article"""
        try:
            import trafilatura
        except ImportError:
            raise ImportError("Install trafilatura: pip install trafilatura")
        
        import urllib.request
        
        # Download the page
        req = urllib.request.Request(url, headers={"User-Agent": "Cortex/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        
        # Extract readable content
        content = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            include_links=True,
        )
        
        if not content:
            raise ValueError(f"Could not extract content from {url}")
        
        # Generate title from URL
        title = url.split("/")[-1].replace("-", " ").replace(".html", "").replace("_", " ").title()
        
        # Create markdown
        md_content = f"# {title}\n\n"
        md_content += f"_Source: {url}_\n\n"
        md_content += f"_Ingested: {time.strftime('%Y-%m-%d')}_\n\n"
        md_content += "---\n\n"
        md_content += content
        
        # Save to raw/articles
        slug = self._slugify(title)
        raw_path = self.kb.raw_path / "articles" / f"{slug}.md"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(md_content)
        
        # Create wiki summary
        wiki_path = f"summaries/{slug}.md"
        self.kb.write_article(wiki_path, md_content)
        
        return IngestResult(
            source_path=url,
            wiki_path=wiki_path,
            title=title,
            word_count=len(content.split()),
            content_type="web",
        )
    
    # === Format-specific ingestors ===
    
    def _ingest_pdf(self, path: Path) -> IngestResult:
        """Ingest a PDF document"""
        try:
            import pdfplumber
        except ImportError:
            raise ImportError("Install pdfplumber: pip install pdfplumber")
        
        text_parts = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
        
        full_text = "\n\n".join(text_parts)
        
        # Generate title from filename or first line
        title = path.stem.replace("-", " ").replace("_", " ").title()
        
        # Create markdown
        md_content = f"# {title}\n\n"
        md_content += f"_Source: {path.name}_\n\n"
        md_content += f"_Ingested: {time.strftime('%Y-%m-%d')}_\n\n"
        md_content += "---\n\n"
        md_content += full_text
        
        # Save to raw/papers
        slug = self._slugify(title)
        raw_path = self.kb.raw_path / "papers" / f"{slug}.md"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(md_content)
        
        # Create wiki summary
        wiki_path = f"summaries/{slug}.md"
        self.kb.write_article(wiki_path, md_content)
        
        return IngestResult(
            source_path=str(path),
            wiki_path=wiki_path,
            title=title,
            word_count=len(full_text.split()),
            content_type="pdf",
        )
    
    def _ingest_text(self, path: Path) -> IngestResult:
        """Ingest a text/markdown file"""
        content = path.read_text()
        title = self._extract_title(content, path.stem)
        
        # Copy to raw/articles
        slug = self._slugify(title)
        raw_path = self.kb.raw_path / "articles" / f"{slug}.md"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(content)
        
        # Create wiki article
        wiki_path = f"summaries/{slug}.md"
        self.kb.write_article(wiki_path, content)
        
        return IngestResult(
            source_path=str(path),
            wiki_path=wiki_path,
            title=title,
            word_count=len(content.split()),
            content_type="text",
        )
    
    def _ingest_html(self, path: Path) -> IngestResult:
        """Ingest an HTML file"""
        try:
            import trafilatura
        except ImportError:
            raise ImportError("Install trafilatura: pip install trafilatura")
        
        html = path.read_text()
        content = trafilatura.extract(html)
        
        if not content:
            content = html  # Fallback to raw HTML
        
        title = path.stem.replace("-", " ").replace("_", " ").title()
        
        md_content = f"# {title}\n\n{content}"
        
        slug = self._slugify(title)
        wiki_path = f"summaries/{slug}.md"
        self.kb.write_article(wiki_path, md_content)
        
        return IngestResult(
            source_path=str(path),
            wiki_path=wiki_path,
            title=title,
            word_count=len(content.split()),
            content_type="web",
        )
    
    def _ingest_code(self, path: Path) -> IngestResult:
        """Ingest a code file"""
        content = path.read_text()
        lang = self._detect_language(path.suffix)
        
        md_content = f"# {path.name}\n\n"
        md_content += f"_Source: {path.name}_\n\n"
        md_content += f"_Language: {lang}_\n\n"
        md_content += f"```{lang}\n{content}\n```\n"
        
        slug = self._slugify(path.stem)
        wiki_path = f"summaries/code-{slug}.md"
        self.kb.write_article(wiki_path, md_content)
        
        return IngestResult(
            source_path=str(path),
            wiki_path=wiki_path,
            title=path.name,
            word_count=len(content.split()),
            content_type="code",
        )
    
    def _ingest_data(self, path: Path) -> IngestResult:
        """Ingest a data file (JSON, YAML, CSV)"""
        ext = path.suffix.lower()
        
        if ext == ".csv":
            import csv
            with open(path) as f:
                reader = csv.reader(f)
                rows = list(reader)
            
            headers = rows[0] if rows else []
            row_count = len(rows) - 1
            
            md_content = f"# {path.name}\n\n"
            md_content += f"_Rows: {row_count:,} | Columns: {len(headers)}_\n\n"
            md_content += "## Schema\n\n"
            md_content += "| Column | Sample |\n|--------|--------|\n"
            for h in headers:
                sample = rows[1][headers.index(h)] if len(rows) > 1 else ""
                md_content += f"| {h} | {sample[:50]} |\n"
            
        elif ext in (".json", ".yaml", ".yml"):
            if ext == ".json":
                data = json.loads(path.read_text())
            else:
                try:
                    import yaml
                    data = yaml.safe_load(path.read_text())
                except ImportError:
                    raise ImportError("Install pyyaml: pip install pyyaml")
            
            if isinstance(data, dict):
                md_content = f"# {path.name}\n\n"
                md_content += "## Structure\n\n"
                for key, value in data.items():
                    md_content += f"- **{key}**: {type(value).__name__}"
                    if isinstance(value, str):
                        md_content += f" = `{value[:100]}`"
                    md_content += "\n"
            elif isinstance(data, list):
                md_content = f"# {path.name}\n\n"
                md_content += f"_Array with {len(data)} items_\n\n"
                if data and isinstance(data[0], dict):
                    md_content += "## Schema\n\n"
                    for key in data[0].keys():
                        md_content += f"- **{key}**\n"
            else:
                md_content = f"# {path.name}\n\n{data}"
        else:
            md_content = f"# {path.name}\n\n"
        
        slug = self._slugify(path.stem)
        wiki_path = f"summaries/data-{slug}.md"
        self.kb.write_article(wiki_path, md_content)
        
        return IngestResult(
            source_path=str(path),
            wiki_path=wiki_path,
            title=path.name,
            word_count=len(md_content.split()),
            content_type="data",
        )
    
    def _ingest_image(self, path: Path) -> IngestResult:
        """Ingest an image file"""
        # Copy to raw/images
        dest = self.kb.raw_path / "images" / path.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(path, dest)
        
        # Create wiki article referencing the image
        slug = self._slugify(path.stem)
        md_content = f"# {path.name}\n\n"
        md_content += f"![{path.name}](../../raw/images/{path.name})\n"
        
        wiki_path = f"summaries/image-{slug}.md"
        self.kb.write_article(wiki_path, md_content)
        
        return IngestResult(
            source_path=str(path),
            wiki_path=wiki_path,
            title=path.name,
            word_count=0,
            content_type="image",
        )
    
    def _ingest_generic(self, path: Path) -> IngestResult:
        """Ingest an unknown file type"""
        content = path.read_text(errors="ignore")
        title = path.stem.replace("-", " ").replace("_", " ").title()
        
        md_content = f"# {title}\n\n"
        md_content += f"_Source: {path.name}_\n\n"
        md_content += f"_Type: {path.suffix}_\n\n"
        md_content += "```\n"
        md_content += content[:5000]  # Limit
        md_content += "\n```\n"
        
        slug = self._slugify(title)
        wiki_path = f"summaries/{slug}.md"
        self.kb.write_article(wiki_path, md_content)
        
        return IngestResult(
            source_path=str(path),
            wiki_path=wiki_path,
            title=title,
            word_count=len(content.split()),
            content_type="generic",
        )
    
    # === Helpers ===
    
    def _slugify(self, text: str) -> str:
        """Convert text to URL-safe slug"""
        text = text.lower().strip()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[\s_-]+', '-', text)
        return text[:100]
    
    def _extract_title(self, content: str, fallback: str) -> str:
        """Extract title from content"""
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return fallback.replace("-", " ").replace("_", " ").title()
    
    def _detect_language(self, ext: str) -> str:
        """Detect programming language from file extension"""
        lang_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".c": "c",
            ".cpp": "cpp",
            ".h": "c",
        }
        return lang_map.get(ext, "text")
