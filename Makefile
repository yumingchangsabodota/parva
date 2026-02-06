.PHONY: build up down logs dev executor-build clean

# Build all containers
build:
	docker compose build
	$(MAKE) executor-build

# Build the executor sidecar image
executor-build:
	docker build -t parva-executor:latest -f backend/executor/Dockerfile backend/executor/

# Start all services
up:
	$(MAKE) executor-build
	docker compose up -d

# Stop all services
down:
	docker compose down

# View logs
logs:
	docker compose logs -f

# Development mode — start infra only, run backend/frontend locally
dev:
	$(MAKE) executor-build
	docker compose up -d postgres redis minio

dev-backend:
	cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

dev-frontend:
	cd frontend && npm run dev

# Clean up everything
clean:
	docker compose down -v --remove-orphans
	docker rm -f $$(docker ps -aq --filter label=parva.role=executor) 2>/dev/null || true
