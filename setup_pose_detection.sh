#!/bin/bash
# Setup script for BJJ Pose Detection

echo "=== BJJ Pose Detection Setup ==="
echo ""

# Check Python version
echo "Checking Python version..."
python3 --version

if [ $? -ne 0 ]; then
    echo "ERROR: Python 3 is not installed"
    exit 1
fi

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
cd "$(dirname "$0")"
pip3 install -r python/requirements.txt

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install Python dependencies"
    exit 1
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "To test the pose detector:"
echo "  python3 python/bjj_pose_detector.py /path/to/video.mp4"
echo ""
echo "To run the full application:"
echo "  mvn spring-boot:run"
