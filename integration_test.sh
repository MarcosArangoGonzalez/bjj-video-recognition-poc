#!/bin/bash

# Configuration
API_URL="http://localhost:8080/api"
USERNAME="poc_user"
PASSWORD="poc_password" # Found in DataInitializer.java
VIDEO_FILE="uploads/005cc9e1-f2ae-4561-ace0-4f0f167b0ec8.mp4"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo "---------------------------------------------------"
echo "Starting Integration Test: BJJ Video Recognition PoC"
echo "---------------------------------------------------"

# 1. Login
echo -n "Step 1: Authenticating... "
TOKEN_RESPONSE=$(curl -s -X POST "$API_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"usernameOrEmail\":\"$USERNAME\",\"password\":\"$PASSWORD\"}")

# robust parsing with grep/sed since jq might be missing
TOKEN=$(echo $TOKEN_RESPONSE | grep -o '"accessToken":"[^"]*' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
    echo -e "${RED}FAILED${NC}"
    echo "Response: $TOKEN_RESPONSE"
    exit 1
fi
echo -e "${GREEN}SUCCESS${NC}"
# echo "Token: ${TOKEN:0:10}..."

# 2. Upload Video
echo -n "Step 2: Uploading Video ($VIDEO_FILE)... "
if [ ! -f "$VIDEO_FILE" ]; then
    echo -e "${RED}Video file not found!${NC}"
    exit 1
fi

UPLOAD_RESPONSE=$(curl -s -X POST "$API_URL/videos/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@$VIDEO_FILE" \
  -F "title=Integration Test Video")

VIDEO_ID=$(echo $UPLOAD_RESPONSE | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)

if [ -z "$VIDEO_ID" ]; then
    echo -e "${RED}FAILED${NC}"
    echo "Response: $UPLOAD_RESPONSE"
    exit 1
fi
echo -e "${GREEN}SUCCESS${NC} (Video ID: $VIDEO_ID)"

# 3. Poll for Analysis Results (Wait for processing)
echo "Step 3: Waiting for Analysis Results (Max 180s)..."
for i in {1..36}; do
    echo -n "Attempt $i: Checking tags... "
    TAGS_RESPONSE=$(curl -s -X GET "$API_URL/videos/$VIDEO_ID/tags" \
      -H "Authorization: Bearer $TOKEN")
    
    # Check if we got tags (look for "id" or specific fields in JSON array)
    TAG_COUNT=$(echo $TAGS_RESPONSE | grep -o '"id":' | wc -l)
    
    if [ "$TAG_COUNT" -gt "0" ]; then
        echo -e "${GREEN}SUCCESS${NC} - Found $TAG_COUNT tags!"
        echo "Sample Tag Response: $TAGS_RESPONSE"
        exit 0
    else
        echo "Pending..."
        sleep 5
    fi
done

echo -e "${RED}TIMEOUT${NC} - Analysis did not complete in time."
exit 1
