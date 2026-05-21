@echo off
REM 2Care.ai Voice AI Agent — Start Script for Windows
REM Ensures Redis is running and starts the FastAPI server

setlocal enabledelayedexpansion

echo.
echo 🚀 Starting 2Care.ai Voice AI Agent...
echo.

REM Check if .env exists
if not exist ".env" (
    echo ⚠️  .env file not found
    echo Creating .env from .env.example...
    copy ".env.example" ".env"
    echo ⚠️  Please update .env with your API keys
    echo.
)

REM Activate virtual environment if it exists
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

REM Install/update dependencies
echo 📦 Ensuring dependencies are installed...
pip install -q -r requirements.txt

REM Start the server
echo.
echo 🔗 Starting FastAPI server on http://localhost:8000
echo 📖 API docs: http://localhost:8000/docs
echo.

uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

pause
