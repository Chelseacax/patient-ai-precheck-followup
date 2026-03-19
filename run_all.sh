#!/usr/bin/env bash
# ============================================================
# run_all.sh — Start all MedBridge components in one command
# Usage: ./run_all.sh
# ============================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  MedBridge — Starting all services          ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── Step 1: Start HealthHub Agent bridge (Playwright browser) ──────────
echo "[1/3] Starting HealthHub Agent Bridge on :7001..."
osascript -e "tell application \"Terminal\" to do script \"cd '$PROJECT_DIR/healthhub_agent' && python3 server.py\""
sleep 2

# ── Step 2: Start MedBridge Flask backend ──────────────────────────────
echo "[2/3] Starting MedBridge Flask backend on :5001..."
osascript -e "tell application \"Terminal\" to do script \"cd '$PROJECT_DIR' && python3 app.py\""
sleep 2

# ── Step 3: Start HealthHub frontend (Vite dev server) ─────────────────
echo "[3/3] Starting HealthHub WebApp frontend on :5173..."
osascript -e "tell application \"Terminal\" to do script \"cd '$PROJECT_DIR/HealthHub WebApp' && npm run dev\""
sleep 3

# ── Open browsers ──────────────────────────────────────────────────────
echo ""
echo "Opening MedBridge in browser..."
open "http://localhost:5001"

echo ""
echo "✅  All services started!"
echo ""
echo "   MedBridge UI  → http://localhost:5001"
echo "   HealthHub App → http://localhost:5173"
echo "   Agent Bridge  → http://localhost:7001"
echo ""
echo "Press Ctrl+C in any terminal window to stop a service."
