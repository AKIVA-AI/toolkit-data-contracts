FROM python:3.11-slim

LABEL maintainer="Toolkit Contributors"
LABEL description="Data Contracts & Drift Detection - Enterprise data quality"

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY pyproject.toml .
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -e ".[dev]"

# Copy application
COPY src/ ./src/
COPY README.md .

# Install package
RUN pip install -e .

# Create non-root user
RUN useradd -m -u 1000 contracts && chown -R contracts:contracts /app
USER contracts

# Create data directory
RUN mkdir -p /app/data

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from toolkit_data_contracts_drift import __version__; print(__version__)" || exit 1

# Default command - show help
CMD ["toolkit-contracts", "--help"]
