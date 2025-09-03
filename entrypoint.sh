#!/bin/bash
# Entrypoint script to launch all services in one container.
set -e

# Start the FastAPI server (LangGraph node API)
uvicorn server.server_api:app --host 0.0.0.0 --port "${PORT:-8080}" &
API_PID=$!

# Start the OPC UA server for G-code publishing
python server/opcua_server.py &
OPCUA_PID=$!

# Start the Streamlit UI.  The --server.headless flag disables
# attempting to open a browser in the container environment.
STREAMLIT_PORT="${STREAMLIT_PORT:-8501}"
streamlit run streamlit.py --server.address 0.0.0.0 --server.port "$STREAMLIT_PORT" --server.headless true &
STREAMLIT_PID=$!

# Wait for any of the background processes to exit.
wait -n $API_PID $OPCUA_PID $STREAMLIT_PID
