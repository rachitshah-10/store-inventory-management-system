# Pinned Python base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Ensure output is sent straight to terminal without buffering
ENV PYTHONUNBUFFERED=1

# Copy dependency requirements first to leverage Docker layer caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Run the interactive menu by default
CMD ["python", "main.py"]

