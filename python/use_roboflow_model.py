"""
Download and use Roboflow pre-trained model weights for inference
This script downloads the trained model from Roboflow (not just the dataset)
"""

from roboflow import Roboflow
from dotenv import load_dotenv
import os

load_dotenv()

def download_roboflow_model(workspace, project, version, api_key=None):
    """
    Download pre-trained model weights from Roboflow
    
    Args:
        workspace: Roboflow workspace name
        project: Roboflow project name
        version: Model version number
        api_key: Roboflow API key (optional, reads from env)
    
    Returns:
        model: Roboflow model object ready for inference
    """
    api_key = api_key or os.getenv('ROBOFLOW_API_KEY')
    if not api_key:
        raise ValueError("ROBOFLOW_API_KEY not found in environment")
    
    print(f"Loading Roboflow model: {workspace}/{project}/v{version}")
    
    # Initialize Roboflow
    rf = Roboflow(api_key=api_key)
    
    # Get the project
    project_obj = rf.workspace(workspace).project(project)
    
    # Get specific version (this is the trained model)
    model = project_obj.version(version).model
    
    print(f"Model loaded successfully!")
    print(f"  Classes: {model.classes if hasattr(model, 'classes') else 'N/A'}")
    
    return model


def run_inference_on_image(model, image_path, confidence=40, overlap=30):
    """
    Run inference on a single image using Roboflow model
    
    Args:
        model: Roboflow model object
        image_path: Path to image file
        confidence: Confidence threshold (0-100)
        overlap: Overlap threshold for NMS (0-100)
    
    Returns:
        predictions: Dictionary with prediction results
    """
    print(f"\nRunning inference on: {image_path}")
    predictions = model.predict(image_path, confidence=confidence, overlap=overlap)
    
    print(f"Predictions: {predictions.json()}")
    return predictions


def evaluate_roboflow_model_on_dataset(workspace, project, version, dataset_path):
    """
    Evaluate Roboflow pre-trained model on validation set
    
    Args:
        workspace: Roboflow workspace
        project: Project name
        version: Model version
        dataset_path: Path to dataset directory (with train/valid/test splits)
    """
    from pathlib import Path
    import json
    
    # Download model
    model = download_roboflow_model(workspace, project, version)
    
    # Find validation images
    valid_images = list(Path(dataset_path).glob('valid/**/*.jpg'))
    if not valid_images:
        valid_images = list(Path(dataset_path).glob('valid/**/*.png'))
    
    print(f"\nFound {len(valid_images)} validation images")
    
    if not valid_images:
        print("No validation images found!")
        return
    
    # Run predictions on a sample
    sample_size = min(10, len(valid_images))
    print(f"\nRunning inference on {sample_size} sample images...")
    
    all_predictions = []
    for img_path in valid_images[:sample_size]:
        try:
            predictions = run_inference_on_image(model, str(img_path))
            all_predictions.append({
                'image': str(img_path),
                'predictions': predictions.json()
            })
        except Exception as e:
            print(f"Error on {img_path}: {e}")
    
    # Save results
    output_file = 'roboflow_model_predictions.json'
    with open(output_file, 'w') as f:
        json.dump(all_predictions, f, indent=2)
    
    print(f"\nResults saved to: {output_file}")
    
    # Print summary
    print("\n" + "="*60)
    print("ROBOFLOW MODEL INFERENCE SUMMARY")
    print("="*60)
    for pred in all_predictions:
        print(f"\nImage: {Path(pred['image']).name}")
        pred_data = pred['predictions']
        if 'predictions' in pred_data:
            for p in pred_data['predictions']:
                print(f"  - {p.get('class', 'unknown')}: {p.get('confidence', 0):.2%} confidence")
        else:
            print("  No predictions")
    
    return all_predictions


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Download and use Roboflow pre-trained models')
    parser.add_argument('--workspace', type=str, default='initialfightdataset',
                       help='Roboflow workspace name')
    parser.add_argument('--project', type=str, default='jiujitsu-8mngi',
                       help='Roboflow project name')
    parser.add_argument('--version', type=int, default=1,
                       help='Model version')
    parser.add_argument('--dataset', type=str, default='../datasets/submissions',
                       help='Path to dataset directory')
    parser.add_argument('--image', type=str, help='Single image to test')
    
    args = parser.parse_args()
    
    if args.image:
        # Test on single image
        model = download_roboflow_model(args.workspace, args.project, args.version)
        run_inference_on_image(model, args.image)
    else:
        # Evaluate on dataset
        evaluate_roboflow_model_on_dataset(
            args.workspace, 
            args.project, 
            args.version,
            args.dataset
        )
