#!/bin/bash
PROJECT_ID="video-intelligence-480312"
REGION="us-central1"

echo "Checking available models for project: $PROJECT_ID in region: $REGION"
echo "----------------------------------------------------------------"

# Check if logged in
ACCOUNT=$(gcloud config get-value account 2>/dev/null)
if [ -z "$ACCOUNT" ]; then
    echo "ERROR: No gcloud account active. Please run 'gcloud auth login' first."
    exit 1
fi

echo "Active account: $ACCOUNT"
echo "----------------------------------------------------------------"

# List models
echo "Listing Gemini models..."
gcloud ai models list-base-models --region=$REGION --project=$PROJECT_ID --format="table(modelId, displayName)" | grep -i gemini

echo "----------------------------------------------------------------"
echo "If the list above is empty, you might need to enable the Generative AI in the Vertex AI dashboard."
