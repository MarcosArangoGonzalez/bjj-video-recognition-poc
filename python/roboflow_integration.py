"""
Roboflow Integration Module
Downloads and integrates BJJ-specific datasets from Roboflow with annotations.json
"""

import os
import json
from pathlib import Path
from roboflow import Roboflow
from dotenv import load_dotenv

load_dotenv()

# Roboflow Model Configuration - BJJ-Positions Master Model
ROBOFLOW_DATASETS = {
    # Primary: BJJ-Positions Master Model (14k+ images)
    "bjj_positions_master": {
        "workspace": "bjj-885sh",
        "project": "bjj-positions-eexsh",
        "version": 2,
        "description": "Master model with comprehensive BJJ technique detection",
        "layer": "primary",
        "priority": 1,
        "features": {
            "submissions": ["armbar", "triangle", "rear_naked_choke", "guillotine", "kimura", "americana"],
            "positions": ["mount", "back_control", "side_control", "guard", "half_guard"],
            "techniques": ["takedown", "sweep"]
        },
        "dataset_size": "14,000+ images",
        "advantages": [
            "Balanced dataset with multiple camera angles",
            "Separates position from technique",
            "Reduces false positives in close contact",
            "Best mAP for submissions"
        ]
    },
    
    # Secondary: Submission Specialist (Confirmation Layer)
    "submission_specialist": {
        "workspace": "ana-beatriz-mdnhg",
        "project": "golpes-jiu-jitsu",
        "version": 1,
        "description": "Specialist for submission confirmation when primary confidence < 50%",
        "layer": "secondary",
        "priority": 2,
        "classes": ["americana", "armlock", "triangle"],
        "trigger_condition": "low_confidence_submissions"
    }
}


class RoboflowIntegration:
    """Handles downloading and preparing Roboflow BJJ datasets"""
    
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv('ROBOFLOW_API_KEY')
        if not self.api_key:
            raise ValueError("ROBOFLOW_API_KEY not found in environment")
        
        self.rf = Roboflow(api_key=self.api_key)
        self.datasets_dir = Path('datasets')
        self.datasets_dir.mkdir(exist_ok=True)
    
    def download_dataset(self, dataset_name, format="yolov8"):
        """
        Download a specific Roboflow dataset
        
        Args:
            dataset_name: One of 'positions', 'segmentation', 'submissions', 'analysis'
            format: Export format (yolov8, coco, etc.)
        
        Returns:
            Path to downloaded dataset
        """
        if dataset_name not in ROBOFLOW_DATASETS:
            raise ValueError(f"Unknown dataset: {dataset_name}")
        
        config = ROBOFLOW_DATASETS[dataset_name]
        
        print(f"Downloading {dataset_name} dataset from Roboflow...")
        project = self.rf.workspace(config["workspace"]).project(config["project"])
        version = project.version(config["version"])
        
        # Download dataset
        dataset_path = self.datasets_dir / dataset_name
        dataset = version.download(format, location=str(dataset_path))
        
        print(f"Downloaded {dataset_name} to {dataset_path}")
        return dataset_path
    
    def download_all_datasets(self):
        """Download all configured Roboflow datasets"""
        downloaded = {}
        
        for dataset_name in ROBOFLOW_DATASETS.keys():
            try:
                path = self.download_dataset(dataset_name)
                downloaded[dataset_name] = str(path)
            except Exception as e:
                print(f"Error downloading {dataset_name}: {str(e)}")
                downloaded[dataset_name] = None
        
        return downloaded
    
    def merge_with_annotations(self, annotations_json_path):
        """
        Merge Roboflow datasets with annotations.json ground truth
        
        Args:
            annotations_json_path: Path to annotations.json file
        
        Returns:
            dict: Merged dataset configuration
        """
        print("Loading annotations.json...")
        with open(annotations_json_path, 'r') as f:
            annotations = json.load(f)
        
        print(f"Loaded {len(annotations)} annotated frames")
        
        # TODO: Implement merging logic
        # This will:
        # 1. Parse Roboflow dataset formats
        # 2. Convert annotations.json to compatible format
        # 3. Create unified training dataset
        # 4. Generate data.yaml for YOLOv8 training
        
        merged_config = {
            "roboflow_samples": self._count_roboflow_samples(),
            "annotations_samples": len(annotations),
            "total": self._count_roboflow_samples() + len(annotations),
            "classes": self._extract_bjj_classes(annotations)
        }
        
        return merged_config
    
    def _count_roboflow_samples(self):
        """Count total samples from Roboflow datasets"""
        total = 0
        for dataset_name in ROBOFLOW_DATASETS.keys():
            dataset_path = self.datasets_dir / dataset_name
            if dataset_path.exists():
                # Count images in train/valid/test splits
                for split in ['train', 'valid', 'test']:
                    split_path = dataset_path / split / 'images'
                    if split_path.exists():
                        total += len(list(split_path.glob('*.jpg'))) + \
                                len(list(split_path.glob('*.png')))
        return total
    
    def _extract_bjj_classes(self, annotations):
        """Extract unique BJJ position classes from annotations.json"""
        positions = set()
        for item in annotations:
            if 'position' in item:
                positions.add(item['position'])
        return sorted(list(positions))
    
    def create_training_config(self, output_path='data.yaml'):
        """
        Create YOLOv8 training configuration file
        
        Args:
            output_path: Path to save data.yaml
        """
        # Placeholder - will be implemented after dataset merge
        config = {
            'path': str(self.datasets_dir.absolute()),
            'train': 'train/images',
            'val': 'valid/images',
            'test': 'test/images',
            'names': {
                0: 'standing',
                1: 'guard',
                2: 'mount',
                3: 'side_control',
                4: 'back_control',
                # ... more positions from merged datasets
            }
        }
        
        with open(output_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        print(f"Training config saved to {output_path}")


def main():
    """Download and prepare BJJ datasets for training"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Download and prepare Roboflow BJJ datasets')
    parser.add_argument('--download', action='store_true', help='Download all datasets')
    parser.add_argument('--merge', type=str, help='Path to annotations.json file')
    parser.add_argument('--config', action='store_true', help='Generate training config')
    
    args = parser.parse_args()
    
    integration = RoboflowIntegration()
    
    if args.download:
        print("Downloading Roboflow datasets...")
        downloaded = integration.download_all_datasets()
        print("Downloaded datasets:", json.dumps(downloaded, indent=2))
    
    if args.merge:
        print(f"Merging with {args.merge}...")
        merged = integration.merge_with_annotations(args.merge)
        print("Merge summary:", json.dumps(merged, indent=2))
    
    if args.config:
        print("Creating training configuration...")
        integration.create_training_config()


if __name__ == '__main__':
    main()
