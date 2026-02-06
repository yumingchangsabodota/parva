# Executor sidecar — lightweight polyglot container for skill execution.
# Supports Python, TypeScript/JavaScript, and Bash skills.
# Uses uv (Python) + Bun (JS/TS) for fast dependency management.

FROM python:3.12-slim

# Install system deps + uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl build-essential bash jq unzip && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Install Bun — fast JS/TS runtime + package manager (replaces Node + npm + tsx)
COPY --from=oven/bun:latest /usr/local/bin/bun /usr/local/bin/bun
RUN ln -s /usr/local/bin/bun /usr/local/bin/bunx

# Pre-install common Python packages + executor server deps
RUN uv pip install --system \
    aiohttp \
    requests httpx pandas numpy matplotlib pillow \
    openpyxl python-docx PyPDF2 beautifulsoup4 lxml \
    pyyaml toml

# Install the executor server
COPY executor_server.py /opt/executor/server.py

WORKDIR /workspace

EXPOSE 8100

CMD ["python", "/opt/executor/server.py"]
