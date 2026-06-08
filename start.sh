#!/usr/bin/env bash
# OCR Service — quick-start script
# Usage: ./start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load .env if it exists
if [ -f "$SCRIPT_DIR/.env" ]; then
  export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
fi

# Check for Tesseract (required unless using Claude Vision)
if ! command -v tesseract &>/dev/null && [ -z "$ANTHROPIC_API_KEY" ]; then
  echo ""
  echo "  Tesseract not found. Install it first:"
  echo "    macOS:  brew install tesseract"
  echo "    Ubuntu: sudo apt install tesseract-ocr"
  echo "  Or set ANTHROPIC_API_KEY in .env to use Claude Vision instead."
  echo ""
  exit 1
fi

# Install backend deps if venv doesn't exist
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv "$SCRIPT_DIR/.venv"
  source "$SCRIPT_DIR/.venv/bin/activate"
  pip install -q --upgrade pip
  pip install -q -r "$SCRIPT_DIR/backend/requirements.txt"
  pip install -q -r "$SCRIPT_DIR/mcp_server/requirements.txt"
else
  source "$SCRIPT_DIR/.venv/bin/activate"
fi

PORT="${PORT:-8000}"
echo ""
echo "  OCR Service starting on http://localhost:$PORT"
echo "  API docs:  http://localhost:$PORT/docs"
echo ""

cd "$SCRIPT_DIR/backend"
python main.py
