#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=========================================================="
echo "🇮🇳 IndicTender Platform - CPPP Public Data Intelligence"
echo "=========================================================="

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 could not be found. Please install Python 3.9+."
    exit 1
fi

# Ensure virtualenv exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment in ./venv..."
    python3 -m venv venv
    ./venv/bin/pip install --upgrade pip
    ./venv/bin/pip install -r requirements.txt
fi

# Run database migrations
echo "🔄 Checking and applying database migrations..."
./venv/bin/python3 -m app.db.migrations

echo "🚀 Starting Indic Tender Web Platform on http://localhost:8000 ..."
echo "📖 OpenAPI Documentation available at http://localhost:8000/docs"
echo "=========================================================="

./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
