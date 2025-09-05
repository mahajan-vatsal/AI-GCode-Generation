# Use official Python 3.12 slim image
FROM python:3.12-slim

# System deps for opencv, cairosvg, pyzbar, etc. + curl for healthcheck
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
        curl \
        git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Leverage cache
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Ensure Python can import from /app
ENV PYTHONPATH=/app \
    PORT=8080 \
    STREAMLIT_PORT=8501 \
    LANGCHAIN_PROJECT="AI-GCode-Generator"

