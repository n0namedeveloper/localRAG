FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Install system dependencies for tree-sitter and git
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    build-essential \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .

# Install dependencies using uv into the system python
RUN uv pip install --system .

COPY app/ ./app/
RUN mkdir -p grammars/

ENV PYTHONPATH=/app
ENV DATA_DIR=/app/data
ENV GRAMMARS_DIR=/app/grammars

EXPOSE 8000
