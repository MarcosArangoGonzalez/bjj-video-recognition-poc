"""
Evaluate YOLOv8 model performance on Roboflow submissions dataset
Tests detection precision, recall, and mAP for BJJ submission techniques
"""

import sys
from pathlib import Path
from ultralytics import YOLO
import yaml

def evaluate_submissions_dataset(dataset_yaml_path, model_path='yolov8n.pt'):
    """
    Evaluate YOLOv8 model on submissions dataset
    
    Args:
        dataset_yaml_path: Path to data.yaml
        model_path: Path to YOLOv8 model (default: base model)
    """
    print(f"Evaluating YOLOv8 model on submissions dataset...")
    print(f"Dataset config: {dataset_yaml_path}")
    print(f"Model: {model_path}")
    
    # Load dataset configuration
    with open(dataset_yaml_path, 'r') as f:
        data_config = yaml.safe_load(f)
    
    print(f"\nDataset info:")
    print(f"  Classes ({data_config['nc']}): {', '.join(data_config['names'])}")
    
    # Load model
    print(f"\nLoading model: {model_path}")
    model = YOLO(model_path)
    
    # Run validation on the dataset
    print("\nRunning validation...")
    results = model.val(
        data=dataset_yaml_path,
        imgsz=640,
        batch=16,
        conf=0.25,
        iou=0.45,
        device='cpu',
        plots=True,
        save_json=True
    )
    
    # Print results
    print("\n" + "="*60)
    print("EVALUATION RESULTS - Submissions Dataset")
    print("="*60)
    
    # Overall metrics
    print(f"\nOverall Performance:")
    print(f"  mAP50: {results.box.map50:.3f}")
    print(f"  mAP50-95: {results.box.map:.3f}")
    print(f"  Precision: {results.box.p.mean():.3f}")
    print(f"  Recall: {results.box.r.mean():.3f}")
    
    # Per-class metrics
    print(f"\nPer-Class Performance:")
    print(f"{'Class':<20} {'Precision':<12} {'Recall':<12} {'mAP50':<12}")
    print("-" * 60)
    
    class_names = data_config['names']
    for i, class_name in enumerate(class_names):
        if i < len(results.box.p):
            precision = results.box.p[i] if results.box.p[i] is not None else 0
            recall = results.box.r[i] if results.box.r[i] is not None else 0
            map50 = results.box.ap50[i] if results.box.ap50[i] is not None else 0
            print(f"{class_name:<20} {precision:<12.3f} {recall:<12.3f} {map50:<12.3f}")
    
    print("\n" + "="*60)
    print(f"Validation complete! Results saved to: runs/detect/val/")
    print("="*60)
    
    return results


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Evaluate YOLOv8 on submissions dataset')
    parser.add_argument('--dataset', type=str, 
                       default='../datasets/submissions/data.yaml',
                       help='Path to dataset YAML file')
    parser.add_argument('--model', type=str,
                       default='yolov8n.pt',
                       help='Path to YOLOv8 model weights')
    
    args = parser.parse_args()
    
    # Resolve paths
    dataset_path = Path(args.dataset).resolve()
    
    if not dataset_path.exists():
        print(f"Error: Dataset file not found: {dataset_path}")
        sys.exit(1)
    
    evaluate_submissions_dataset(str(dataset_path), args.model)
