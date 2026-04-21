FROM python:3.11-slim

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir uvicorn  # Ensure uvicorn is available

# Copy application code
COPY . .

# Start Uvicorn. Use shell form so $PORT is evaluated.
# Render dynamically sets $PORT, usually to 10000.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
