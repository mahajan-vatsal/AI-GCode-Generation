# Use official Python 3.12 slim image as a base.  Python ≥ 3.12 is required by this project.
FROM python:3.12-slim

# Install system dependencies needed for packages like opencv‑python, cairosvg, pyzbar, etc.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libgl1 \
        libglx-mesa0 \
        libglib2.0-0 \
        libzbar0 \
        libcairo2 \
        libpango-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        libgdk-pixbuf-xlib-2.0-0 \
        git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies (including streamlit and opcua, which were added)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Copy the entrypoint script and make it executable
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Provide sensible defaults for environment variables.
ENV PORT=8080 \
    STREAMLIT_PORT=8501 \
    LANGCHAIN_PROJECT="AI-GCode-Generator"

# Use the entrypoint script to run all services (FastAPI, OPC UA and Streamlit)
CMD ["/bin/bash", "/app/entrypoint.sh"]
