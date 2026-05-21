#!/bin/bash
# 2Care.ai Voice AI Agent — Start Script
# Ensures Redis is running and starts the FastAPI server

set -e

echo "🚀 Starting 2Care.ai Voice AI Agent..."

# Check if Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo "⚠️  Redis not found on localhost:6379"
    echo "Starting Redis in Docker..."
    docker run -d -p 6379:6379 --name voice-ai-redis redis:7-alpine
    echo "✓ Redis started"
fi

# Load environment
if [ ! -f .env ]; then
    echo "⚠️  .env file not found"
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "⚠️  Please update .env with your API keys"
fi

# Activate virtual environment if it exists
if [ -d .venv ]; then
    source .venv/bin/activate
fi

# Install/update dependencies
echo "📦 Ensuring dependencies are installed..."
pip install -q -r requirements.txt

# Run the server
echo "🔗 Starting FastAPI server on http://localhost:8000"
echo "📖 API docs: http://localhost:8000/docs"
echo ""

uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
