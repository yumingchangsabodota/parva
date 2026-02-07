#!/bin/bash
set -e

echo "==> Building executor image..."
docker build -t parva-executor:latest ./backend/executor

echo "==> Starting all services..."
docker compose up -d --build

echo "==> Waiting for services to be healthy..."
timeout 120 bash -c 'until docker compose ps --format json | grep -q "healthy"; do sleep 2; done' || true

echo ""
echo "============================================"
echo "  Parva is running!"
echo "============================================"
echo "  Frontend:      http://localhost:3000"
echo "  Backend API:   http://localhost:8000/docs"
echo "  LiteLLM:       http://localhost:4000"
echo "  MinIO Console: http://localhost:9001"
echo ""
echo "  Set LLM provider keys as Codespace secrets:"
echo "    OPENAI_API_KEY, ANTHROPIC_API_KEY"
echo "============================================"
