FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY cortex/ ./cortex/
COPY cortex_cli/ ./cortex_cli/

# Install Cortex
RUN pip install --no-cache-dir -e .

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run API server
CMD ["uvicorn", "cortex.api:app", "--host", "0.0.0.0", "--port", "8080"]
