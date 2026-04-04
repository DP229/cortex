"""
Cortex Configuration - Persistent YAML-based config

Provides:
- Wiki path configuration
- LLM provider settings  
- Ingest pipeline options
- Security settings
- File-based persistence

Example:
    config = CortexConfig.load()
    config.llm.model = "llama3.1"
    config.save()
"""

import os
import yaml
from dataclasses import dataclass, field, asdict
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


@dataclass
class WikiConfig:
    """Wiki directory configuration"""
    path: str = "./wiki"
    raw_path: str = "./raw"
    outputs_path: str = "./outputs"
    max_article_tokens: int = 4000
    auto_backlinks: bool = True
    wikilinks: bool = False  # Use standard markdown links


@dataclass
class LLMConfig:
    """LLM provider configuration"""
    provider: str = "ollama"  # ollama, openai, anthropic, groq, openrouter
    model: str = "llama3"
    temperature: float = 0.7
    max_tokens: int = 4096
    max_context_tokens: int = 8192
    api_key: Optional[str] = None
    base_url: Optional[str] = None


@dataclass
class IngestConfig:
    """Ingest pipeline configuration"""
    supported_formats: List[str] = field(default_factory=lambda: [
        ".pdf", ".md", ".txt", ".html", ".py", ".js", ".ts",
        ".go", ".rs", ".java", ".json", ".yaml", ".yml", ".csv",
        ".png", ".jpg", ".jpeg", ".gif", ".svg",
    ])
    max_file_size_mb: int = 50
    exclude_patterns: List[str] = field(default_factory=lambda: [
        "node_modules", ".git", "__pycache__", "*.pyc",
        ".venv", "venv", "dist", "build",
    ])


@dataclass
class SecurityConfig:
    """Security configuration"""
    chroot_wiki: bool = True
    chroot_raw: bool = True
    bash_enabled: bool = False
    web_fetch_allowlist: List[str] = field(default_factory=list)


@dataclass
class CortexConfig:
    """Top-level configuration"""
    wiki: WikiConfig = field(default_factory=WikiConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    ingest: IngestConfig = field(default_factory=IngestConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    _config_path: Optional[str] = None

    @classmethod
    def load(cls, path: Optional[str] = None) -> "CortexConfig":
        """Load config from YAML file"""
        config_path = path or os.path.expanduser("~/.cortex/config.yaml")

        if not os.path.exists(config_path):
            config = cls()
            config._config_path = config_path
            config.save()
            logger.info(f"Created default config at {config_path}")
            return config

        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}

        config = cls(
            wiki=WikiConfig(**data.get("wiki", {})),
            llm=LLMConfig(**data.get("llm", {})),
            ingest=IngestConfig(**data.get("ingest", {})),
            security=SecurityConfig(**data.get("security", {})),
        )
        config._config_path = config_path
        return config

    def save(self):
        """Save config to YAML file"""
        if not self._config_path:
            self._config_path = os.path.expanduser("~/.cortex/config.yaml")

        os.makedirs(os.path.dirname(self._config_path), exist_ok=True)

        data = {
            "wiki": asdict(self.wiki),
            "llm": asdict(self.llm),
            "ingest": asdict(self.ingest),
            "security": asdict(self.security),
        }

        with open(self._config_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, indent=2)

    @property
    def config_dir(self) -> str:
        """Get config directory"""
        return os.path.expanduser("~/.cortex")
