#!/usr/bin/env bash
# Quick iteration test suite for import feature

set -e

echo "🧪 Running import feature tests..."
echo ""

echo "1️⃣  Batching logic (no UI needed):"
.venv/bin/python -m pytest tests/test_import_batching.py -q
echo ""

echo "2️⃣  Import fetch worker:"
.venv/bin/python -m pytest tests/test_import_fetch_worker.py -q
echo ""

echo "3️⃣  Thread shutdown safety:"
.venv/bin/python -m pytest tests/test_import_shutdown.py -q
echo ""

echo "✅ All import feature tests passed!"
