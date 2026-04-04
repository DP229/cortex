"""Tests for config"""
import tempfile
import os
from cortex.config import CortexConfig


def test_default_config():
    config = CortexConfig()
    assert config.wiki.path == "./wiki"
    assert config.llm.provider == "ollama"
    assert config.llm.model == "llama3"
    assert not config.security.bash_enabled


def test_config_save_load():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.yaml")
        
        config = CortexConfig()
        config.llm.model = "llama3.1"
        config.wiki.path = "/tmp/test-wiki"
        config._config_path = config_path
        config.save()
        
        loaded = CortexConfig.load(config_path)
        assert loaded.llm.model == "llama3.1"
        assert loaded.wiki.path == "/tmp/test-wiki"


def test_config_auto_creates_default():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.yaml")
        config = CortexConfig.load(config_path)
        
        assert os.path.exists(config_path)
        assert config.llm.provider == "ollama"
