# Contributing to Cortex

We welcome contributions! Here's how to get started.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/dp229/cortex.git
cd cortex

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Install additional dependencies
pip install ollama  # For local inference
pip install openai anthropic  # For cloud models
```

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=cortex --cov-report=html

# Run specific test file
pytest tests/test_agent.py -v
```

## Code Style

We use:
- **ruff** for linting
- **black** for formatting
- **mypy** for type checking

```bash
# Format code
black cortex/

# Lint
ruff check cortex/

# Type check
mypy cortex/ --ignore-missing-imports
```

## Project Structure

```
cortex/
├── cortex/           # Main package
│   ├── __init__.py       # Package init
│   ├── agent.py          # Core agent
│   ├── brain.py          # LLM interface
│   ├── memory.py         # Memory layer
│   ├── config.py         # Configuration
│   └── knowledgebase.py  # Wiki knowledge base
├── examples/             # Example scripts
├── tests/                # Test suite
└── docs/                 # Documentation
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Commit with clear messages
7. Push to your fork
8. Open a Pull Request

## Commit Message Format

```
type(scope): description

Types:
- feat: New feature
- fix: Bug fix
- docs: Documentation
- style: Formatting
- refactor: Code refactoring
- test: Testing
- chore: Maintenance

Example:
feat(agent): Add memory persistence support
```

## Reporting Issues

Please report issues on GitHub with:
- Clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Your environment (Python version, OS, etc.)

## Questions?

Open an issue or reach out on Discord.

---

Thank you for contributing! 🚀
