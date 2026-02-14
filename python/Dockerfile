FROM pytorch/pytorch:2.0.0-cuda11.7-cudnn8-runtime

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for models and temp files
RUN mkdir -p models temp_frames

# Download base YOLOv8 pose model (will be fine-tuned later)
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n-pose.pt')"

# Expose port
EXPOSE 8081

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8081/health')"

# Run the application
CMD ["gunicorn", "--bind", "0.0.0.0:8081", "--timeout", "300", "--workers", "2", "yolov8_service:app"]
