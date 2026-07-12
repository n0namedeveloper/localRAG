FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for tree-sitter
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    build-essential \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
RUN mkdir -p grammars/

ENV PYTHONPATH=/app/backend
ENV DATA_DIR=/app/data
ENV GRAMMARS_DIR=/app/grammars

EXPOSE 8000