#!/bin/bash
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$PROJECT_ROOT"

echo "🛑 Stopping all MedBridge / HealthHub services..."

# Kill services on 5001 (app.py)
PORT_5001=$(lsof -t -i:5001)
if [ ! -z "$PORT_5001" ]; then
  echo "Stopping app.py on port 5001 (PIDs: $PORT_5001)..."
  kill -9 $PORT_5001
fi

# Kill services on 7001 (server.py)
PORT_7001=$(lsof -t -i:7001)
if [ ! -z "$PORT_7001" ]; then
  echo "Stopping bridge server.py on port 7001 (PIDs: $PORT_7001)..."
  kill -9 $PORT_7001
fi

# General cleanup
pkill -f "python3 server.py" 2>/dev/null
pkill -f "python3 app.py" 2>/dev/null

echo "✅ All services stopped."
