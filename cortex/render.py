"""
Cortex Output Renderer - Render wiki content in various formats

Supports:
- Marp slides (markdown → HTML slides)
- Matplotlib charts (Python code → PNG)
- Mermaid diagrams (markdown → SVG/HTML)
- PDF reports (markdown → PDF via weasyprint/pandoc)

Usage:
    renderer = OutputRenderer("./outputs")
    renderer.render_marp(markdown_content, "slides.html")
    renderer.render_matplotlib(python_code, "chart.png")
"""

import re
import subprocess
import hashlib
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class OutputRenderer:
    """Render wiki content in various output formats."""
    
    def __init__(self, outputs_path: str = "./outputs"):
        self.outputs_path = Path(outputs_path).resolve()
        self.outputs_path.mkdir(parents=True, exist_ok=True)
    
    def render_marp(self, markdown: str, output_path: Optional[str] = None) -> str:
        """Render markdown as Marp-style HTML slides"""
        # Add Marp frontmatter if not present
        if "---" not in markdown[:100]:
            markdown = "---\nmarp: true\ntheme: default\n---\n\n" + markdown
        
        if output_path is None:
            output_path = str(self.outputs_path / "slides.html")
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        html_content = self._markdown_to_html_slides(markdown)
        output_file.write_text(html_content)
        
        return str(output_file)
    
    def _markdown_to_html_slides(self, markdown: str) -> str:
        """Convert marp markdown to HTML slides"""
        # Split by --- separators
        slides = re.split(r'\n---\n', markdown)
        
        html_parts = ["""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
        section {
            font-family: 'Inter', sans-serif;
            padding: 40px;
            font-size: 24px;
            line-height: 1.6;
        }
        h1 { font-size: 2em; color: #1a1a2e; }
        h2 { font-size: 1.5em; color: #16213e; }
        code { background: #f0f0f0; padding: 2px 6px; border-radius: 4px; }
        pre { background: #f8f8f8; padding: 16px; border-radius: 8px; overflow-x: auto; }
    </style>
</head>
<body>
"""]
        
        for slide in slides:
            slide = slide.strip()
            if not slide:
                continue
            # Remove Marp frontmatter
            slide = re.sub(r'^---\n.*?\n---\n', '', slide, flags=re.DOTALL)
            html_slide = f"<section>\n{self._simple_md_to_html(slide)}\n</section>\n"
            html_parts.append(html_slide)
        
        html_parts.append("</body>\n</html>")
        return "\n".join(html_parts)
    
    def _simple_md_to_html(self, markdown: str) -> str:
        """Simple markdown to HTML conversion"""
        html = markdown
        
        # Code blocks
        html = re.sub(
            r'```(\w*)\n(.*?)```',
            r'<pre><code class="language-\1">\2</code></pre>',
            html, flags=re.DOTALL
        )
        
        # Headings
        html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        
        # Bold and italic
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
        
        # Lists
        html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        
        # Line breaks
        html = html.replace('\n\n', '</p><p>').replace('\n', '<br>')
        
        return f"<p>{html}</p>"
    
    def render_matplotlib(self, python_code: str, output_path: Optional[str] = None) -> str:
        """Execute matplotlib code and save the chart"""
        if output_path is None:
            hash_id = hashlib.md5(python_code.encode()).hexdigest()[:8]
            output_path = str(self.outputs_path / f"chart-{hash_id}.png")
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Wrap code to save to file
        wrapped_code = f"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

{python_code}

plt.savefig('{output_path}', dpi=150, bbox_inches='tight')
plt.close()
"""
        try:
            result = subprocess.run(
                ["python", "-c", wrapped_code],
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode != 0:
                logger.error(f"Matplotlib execution failed: {result.stderr}")
                return ""
            
            return str(output_file)
        except Exception as e:
            logger.error(f"Matplotlib rendering error: {e}")
            return ""
    
    def render_mermaid(self, mermaid_code: str, output_path: Optional[str] = None) -> str:
        """Render a Mermaid diagram as HTML"""
        if output_path is None:
            output_path = str(self.outputs_path / "diagram.html")
        
        output_file = Path(output_path)
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
</head>
<body>
    <div class="mermaid">
{mermaid_code}
    </div>
    <script>mermaid.initialize({{ startOnLoad: true }});</script>
</body>
</html>"""
        
        output_file.write_text(html)
        return str(output_file)
    
    def render_pdf(self, markdown: str, output_path: Optional[str] = None) -> str:
        """Render markdown as PDF (requires weasyprint or pandoc)"""
        if output_path is None:
            output_path = str(self.outputs_path / "report.pdf")
        
        output_file = Path(output_path)
        
        # Try pandoc first
        try:
            result = subprocess.run(
                ["pandoc", "-t", "html"],
                input=markdown,
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode == 0:
                html = result.stdout
                # Use weasyprint for PDF
                try:
                    from weasyprint import HTML
                    HTML(string=html).write_pdf(str(output_file))
                    return str(output_file)
                except ImportError:
                    logger.warning("weasyprint not installed. Install: pip install weasyprint")
        except FileNotFoundError:
            logger.warning("pandoc not installed. Install: apt install pandoc")
        
        # Fallback: save as markdown
        md_path = output_path.replace(".pdf", ".md")
        Path(md_path).write_text(markdown)
        return md_path
