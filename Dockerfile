# Use an official Python runtime as a parent image (pinned to stable bookworm)
FROM python:3.11-slim-bookworm

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
# libgl1 and libglib2.0-0 are for OpenCV
# libgomp1 is for FAISS/OpenMP
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    g++ \
    && apt-get clean && rm -rf /var/lib/apt/lists/*


# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . /app/

# The application is expected to run on port 8000
EXPOSE 8000

# Entrypoint will be handled by Docker Compose (e.g., runserver or gunicorn)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
