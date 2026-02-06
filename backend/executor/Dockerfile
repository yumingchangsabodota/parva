# Executor sidecar — lightweight Python container that runs inside user containers.
# It exposes a small HTTP API for receiving skill execution commands.

FROM python:3.12-slim

# Install system deps + uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Pre-install common data science / utility packages + executor server deps
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
