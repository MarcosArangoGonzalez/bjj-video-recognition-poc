#!/bin/bash

# BJJ YOLOv8 Service Setup Script
# Downloads Roboflow datasets and prepares the Python microservice

set -e

echo "=== BJJ YOLOv8 Service Setup ==="
echo

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

# Navigate to python directory
cd "$(dirname "$0")/python"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Check for .env file
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo ""
    echo "⚠️  IMPORTANT: Edit python/.env and add your ROBOFLOW_API_KEY"
    echo "   Get your API key from: https://roboflow.com/settings/api"
    echo ""
fi

# Create necessary directories
mkdir -p models temp_frames datasets

# Download base YOLOv8 model
echo "Downloading base YOLOv8 pose model..."
python3 -c "from ultralytics import YOLO; YOLO('yolov8n-pose.pt')"

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit python/.env and add your ROBOFLOW_API_KEY"
echo "2. Download Roboflow datasets:"
echo "   python3 roboflow_integration.py --download"
echo "3. Merge with annotations.json:"
echo "   python3 roboflow_integration.py --merge ../annotations.json"
echo "4. Start the service:"
echo "   python3 yolov8_service.py"
echo "   OR use Docker: docker-compose up yolov8-service"
echo ""
