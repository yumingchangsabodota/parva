# Executor sidecar — lightweight polyglot container for skill execution.
# Supports Python, TypeScript/JavaScript, and Bash skills.

FROM python:3.12-slim

# Install system deps + uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl build-essential bash jq && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Install Node.js 22 LTS + tsx (TypeScript runner — zero-config, no compile step)
COPY --from=node:22-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:22-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm && \
    npm install -g tsx

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
