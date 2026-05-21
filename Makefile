.PHONY: help install dev test lint format clean run run-docker

help:
	@echo "2Care.ai Voice AI Agent — Development Commands"
	@echo ""
	@echo "Commands:"
	@echo "  make install       Install dependencies"
	@echo "  make dev           Run development server with hot reload"
	@echo "  make test          Run pytest suite"
	@echo "  make test-watch    Run tests in watch mode"
	@echo "  make lint          Check code with pylint/flake8"
	@echo "  make format        Auto-format code with black"
	@echo "  make clean         Remove build artifacts and cache"
	@echo "  make run-docker    Build and run with Docker Compose"
	@echo ""

install:
	pip install -r requirements.txt

dev:
	uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest -v

test-watch:
	pytest -v --tb=short --looponfail

lint:
	pylint backend agent services memory scheduler --disable=all --enable=E,F

format:
	black . --line-length=100

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .venv -prune -o -name "*.pyc" -exec rm -f {} + 2>/dev/null || true
	rm -rf dist build *.egg-info

run-docker:
	docker-compose up --build

.DEFAULT_GOAL := help
