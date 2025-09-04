#!/bin/bash
set -e

# --- FastAPI ---
uvicorn server.server_api:app --host 0.0.0.0 --port "${PORT:-8080}" &
API_PID=$!

# --- OPC UA ---
python server/opcua_server.py &
OPCUA_PID=$!

# --- Streamlit ---
STREAMLIT_PORT="${STREAMLIT_PORT:-8501}"

# Order matters: first match wins. Override with -e STREAMLIT_APP=path.py
CANDIDATES=(
  "${STREAMLIT_APP:-}"
  "server/streamlit.py"
  "client_hmi.py"
  "streamlit.py"
  "ui/streamlit_app.py"
)

FOUND_APP=""
for c in "${CANDIDATES[@]}"; do
  if [ -n "$c" ] && [ -f "$c" ]; then
    FOUND_APP="$c"
    break
  fi
done

if [ -n "$FOUND_APP" ]; then
  echo "[entrypoint] Starting Streamlit app: $FOUND_APP on port $STREAMLIT_PORT"
  streamlit run "$FOUND_APP" --server.address 0.0.0.0 --server.port "$STREAMLIT_PORT" --server.headless true &
  STREAMLIT_PID=$!
else
  echo "[entrypoint] WARNING: No Streamlit app found. Set -e STREAMLIT_APP=your_file.py"
fi

wait -n $API_PID ${OPCUA_PID:-} ${STREAMLIT_PID:-}
