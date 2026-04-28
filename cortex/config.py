"""
Cortex Configuration - Persistent YAML-based config

Provides:
- Wiki path configuration
- LLM provider settings
- Ingest pipeline options
- Security settings
- File-based persistence
- Railway safety compliance settings (EN 50128)

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
class RailwayConfig:
    """
    Railway safety compliance configuration (EN 50128 Class B).

    Settings for document retention, incident management,
    and safety requirement traceability.
    """
    # Authentication
    jwt_secret: str = "change-me-in-production-use-long-random-string"
    jwt_expiration_minutes: int = 15
    jwt_refresh_expiration_days: int = 7
    password_min_length: int = 12
    max_login_attempts: int = 5
    login_lockout_minutes: int = 15

    # EN 50128 Retention Policy
    data_retention_years: int = 10  # EN 50128 requires minimum 10 years for safety records
    document_retention_years: int = 10
    audit_log_retention_years: int = 10

    # IEC 62443 Incident Response
    incident_notification_days: int = 24  # 24-hour reporting window per IEC 62443
    safety_incident_escalation_hours: int = 4  # Critical incidents escalate within 4 hours

    # Security
    encryption_key: Optional[str] = None
    audit_log_enabled: bool = True

    @classmethod
    def from_env(cls) -> "RailwayConfig":
        """Load railway config from environment"""
        return cls(
            jwt_secret=os.getenv("JWT_SECRET", "change-me-in-production-use-long-random-string"),
            jwt_expiration_minutes=int(os.getenv("JWT_EXPIRATION_MINUTES", "15")),
            jwt_refresh_expiration_days=int(os.getenv("JWT_REFRESH_EXPIRATION_DAYS", "7")),
            password_min_length=int(os.getenv("PASSWORD_MIN_LENGTH", "12")),
            max_login_attempts=int(os.getenv("MAX_LOGIN_ATTEMPTS", "5")),
            login_lockout_minutes=int(os.getenv("LOGIN_LOCKOUT_MINUTES", "15")),
            data_retention_years=int(os.getenv("DATA_RETENTION_YEARS", "10")),
            document_retention_years=int(os.getenv("DOCUMENT_RETENTION_YEARS", "10")),
            audit_log_retention_years=int(os.getenv("AUDIT_LOG_RETENTION_YEARS", "10")),
            incident_notification_days=int(os.getenv("INCIDENT_NOTIFICATION_DAYS", "24")),
            safety_incident_escalation_hours=int(os.getenv("SAFETY_INCIDENT_ESCALATION_HOURS", "4")),
            encryption_key=os.getenv("ENCRYPTION_KEY"),
            audit_log_enabled=os.getenv("AUDIT_LOG_ENABLED", "true").lower() == "true",
        )


@dataclass
class CortexConfig:
    """Top-level configuration"""
    wiki: WikiConfig = field(default_factory=WikiConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    ingest: IngestConfig = field(default_factory=IngestConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    railway: RailwayConfig = field(default_factory=RailwayConfig)
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
            railway=RailwayConfig(**data.get("railway", {})),
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
            "railway": asdict(self.railway),
        }

        with open(self._config_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, indent=2)

    @property
    def config_dir(self) -> str:
        """Get config directory"""
        return os.path.expanduser("~/.cortex")
