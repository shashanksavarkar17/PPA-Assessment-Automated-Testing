# Hey developer! We use Python 3.10-slim to keep the base image tiny (~120MB).
FROM python:3.10-slim

# Avoid writing compiled byte code and ensure stdout is unbuffered.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install Chromium and Chromium-Driver directly from the Debian repositories.
# This automatically handles all dependencies and is drastically smaller than Google Chrome Stable (~300MB total install).
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/* /var/lib/dpkg/info/*

# Let's set up a working directory named /app inside the container.
WORKDIR /app

# Copy the requirements file first to maximize Docker build caching efficiency!
COPY requirements.txt .

# Install the Python dependencies listed in requirements.txt (clearing cache immediately).
RUN pip install --no-cache-dir -r requirements.txt

# Copy all our Python solver files and modules.
COPY . .

# Finally, execute our assessment solver orchestrator when the container starts up!
CMD ["python", "main.py"]
