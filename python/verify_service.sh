#!/bin/bash

# Configuration
URL="http://localhost:8081"
MAX_RETRIES=30
SLEEP_TIME=2

echo "Waiting for YOLOv8 service to be ready at $URL..."

# Wait for service to be healthy
for ((i=1;i<=MAX_RETRIES;i++)); do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" $URL/health)
    if [ "$HTTP_CODE" == "200" ]; then
        echo "✅ Service is UP and HEALTHY!"
        curl -s $URL/health | jq .
        exit 0
    else
        echo "Attempt $i/$MAX_RETRIES: Service not ready (HTTP $HTTP_CODE). Retrying inside $SLEEP_TIME seconds..."
        sleep $SLEEP_TIME
    fi
done

echo "❌ Service failed to become healthy after $((MAX_RETRIES * SLEEP_TIME)) seconds."
exit 1
