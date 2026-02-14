#!/bin/bash

# Script para probar el análisis de video con prompt geométrico
# Uso: ./test_geometric_prompt.sh [VIDEO_FILE]

set -e

VIDEO_FILE="${1:-test_video.mp4}"
API_URL="http://localhost:8080"

echo "🔬 Testing BJJ Video Analysis with GEOMETRIC Prompt"
echo "=================================================="
echo ""

# Step 1: Login and get token
echo "📝 Step 1: Logging in..."
LOGIN_RESPONSE=$(curl -s -X POST "$API_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "pocuser",
    "password": "pocpass"
  }')

TOKEN=$(echo $LOGIN_RESPONSE | grep -o '"token":"[^"]*' | sed 's/"token":"//')

if [ -z "$TOKEN" ]; then
  echo "❌ ERROR: Login failed!"
  echo "Response: $LOGIN_RESPONSE"
  exit 1
fi

echo "✅ Login successful! Token obtained."
echo ""

# Step 2: Upload and analyze video
if [ ! -f "$VIDEO_FILE" ]; then
  echo "⚠️  WARNING: Video file '$VIDEO_FILE' not found!"
  echo "Please provide a valid video file as argument:"
  echo "  ./test_geometric_prompt.sh path/to/video.mp4"
  exit 1
fi

echo "📹 Step 2: Uploading video: $VIDEO_FILE"
echo "   Using GEOMETRIC prompt strategy..."
echo ""

ANALYSIS_RESPONSE=$(curl -s -X POST "$API_URL/api/videos/analyze" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@$VIDEO_FILE")

echo "📊 Analysis Response:"
echo "===================="
echo "$ANALYSIS_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$ANALYSIS_RESPONSE"
echo ""

# Check for geometric_evidence in response
if echo "$ANALYSIS_RESPONSE" | grep -q "geometric_evidence"; then
  echo "✅ SUCCESS: Geometric evidence detected in response!"
  echo "   The GEOMETRIC prompt is working correctly."
else
  echo "⚠️  INFO: No geometric_evidence field found."
  echo "   This might be normal if the AI didn't include it in the response,"
  echo "   or if no techniques were detected."
fi

echo ""
echo "🔍 Analysis complete! Check the response above for:"
echo "  - geometric_evidence: { hip_angle, elevation_diff, key_vectors }"
echo "  - observed_mechanics: Visual cues"
echo "  - detail: Geometric reasoning"
