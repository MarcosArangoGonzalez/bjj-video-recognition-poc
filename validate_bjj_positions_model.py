"""
Run validation of BJJ-Positions Roboflow model against annotations.json
"""

from roboflow import Roboflow
import json
import random
from pathlib import Path
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix
import numpy as np

# Load API key
from dotenv import load_dotenv
import os
load_dotenv()

API_KEY = os.getenv('ROBOFLOW_API_KEY')

# Initialize Roboflow
rf = Roboflow(api_key=API_KEY)
project = rf.workspace("bjj-885sh").project("bjj-positions-eexsh")
model = project.version(2).model

# Load ground truth
with open('annotations.json', 'r') as f:
    annotations = json.load(f)

# Sample 1000 random frames
sample_size = min(1000, len(annotations))
sample = random.sample(annotations, sample_size)

print(f"Validating BJJ-Positions model on {sample_size} frames...")

# Run predictions
predictions = []
ground_truth = []

for i, frame_data in enumerate(sample):
    if i % 100 == 0:
        print(f"Progress: {i}/{sample_size}")
    
    # TODO: Extract frame image from video and run inference
    # For now, this is a placeholder
    # result = model.predict(frame_image, confidence=40)
    
    ground_truth.append(frame_data['position'])
    # predictions.append(result['top_class'])

print("Validation complete!")
# TODO: Calculate and print metrics
