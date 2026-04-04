from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cortex",
    version="0.1.0",
    author="Cortex Team",
    author_email="hello@cortex.dev",
    description="Local-First AI Knowledge Base Agent",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/dp229/cortex",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.10",
    install_requires=[
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0",
        "pydantic>=2.5.0",
        "pyyaml>=6.0",
        "nest-asyncio>=1.5.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-asyncio>=0.21",
            "pytest-cov>=4.0",
            "black>=23.0",
            "ruff>=0.1.0",
            "mypy>=1.0",
        ],
        "openai": [
            "openai>=1.0",
        ],
        "anthropic": [
            "anthropic>=0.8",
        ],
        "redis": [
            "redis>=5.0",
        ],
        "vector": [
            "qdrant-client>=1.7",
            "sentence-transformers>=2.2.0",
        ],
        "ingest": [
            "pdfplumber>=0.10.0",
            "trafilatura>=1.6.0",
        ],
        "render": [
            "weasyprint>=60.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "cortex=cortex_cli.main:main",
        ],
    },
)
