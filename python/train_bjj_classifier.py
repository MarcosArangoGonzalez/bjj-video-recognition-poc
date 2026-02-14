import json
import logging
import argparse
import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def extract_features_from_keypoints(keypoints):
    """
    Extract 35 RESOLUTION-INDEPENDENT features - MUST match hybrid_bjj_detector.py!
    
    Features: All 17 COCO keypoints as (x,y) centered on hip midpoint
    and normalized by body_scale (shoulder-to-hip distance), plus avg confidence.
    
    Total: 17*2 + 1 = 35 features
    
    Args:
        keypoints: List of [x, y, conf] lists (from annotations.json) or dicts
    """
    try:
        if not keypoints or len(keypoints) < 17:
            return None
        
        # Convert to numpy array for easier indexing if it's a list
        # annotations.json has [[x,y,c], ...]
        kp_array = np.array(keypoints)
        
        # Extract meaningful landmarks by index (COCO format)
        # 0: nose, 1: l_eye, 2: r_eye, 3: l_ear, 4: r_ear
        # 5: l_sh, 6: r_sh, 7: l_elb, 8: r_elb, 9: l_wr, 10: r_wr
        # 11: l_hip, 12: r_hip, 13: l_knee, 14: r_knee, 15: l_ank, 16: r_ank
        
        left_shoulder = kp_array[5]
        right_shoulder = kp_array[6]
        left_hip = kp_array[11]
        right_hip = kp_array[12]
        
        # Hip center = origin
        hip_cx = (left_hip[0] + right_hip[0]) / 2
        hip_cy = (left_hip[1] + right_hip[1]) / 2
        
        # Shoulder center for body scale
        sh_cx = (left_shoulder[0] + right_shoulder[0]) / 2
        sh_cy = (left_shoulder[1] + right_shoulder[1]) / 2
        
        # Body scale = shoulder-to-hip distance
        body_scale = np.sqrt((sh_cx - hip_cx)**2 + (sh_cy - hip_cy)**2)
        if body_scale < 1.0: body_scale = 1.0
        
        # All 17 keypoints as relative coordinates
        features = []
        for i in range(17):
            kp = kp_array[i]
            features.append((kp[0] - hip_cx) / body_scale)  # Relative X
            features.append((kp[1] - hip_cy) / body_scale)  # Relative Y
        
        # Average confidence
        avg_conf = np.mean(kp_array[:, 2])
        features.append(avg_conf)
        
        return np.array(features)
        
    except Exception as e:
        # logger.warning(f"Feature extraction error: {e}")
        return None


def prepare_dataset(annotations, sample_size=None):
    """
    Prepare training dataset from annotations
    
    Returns:
        X: Feature matrix (n_samples, n_features)
        y: Position labels (n_samples,)
        label_mapping: Dictionary mapping position names to indices
    """
    logger.info("Extracting features from keypoints...")
    
    features_list = []
    labels_list = []
    
    count = 0
    skipped = 0
    
    for item in annotations:
        if sample_size and count >= sample_size:
            break
            
        if 'pose2' not in item or 'position' not in item:
            skipped += 1
            continue
        
        # Parse keypoints
        pose2 = item['pose2']
        if len(pose2) != 17:
            skipped += 1
            continue
            
        features = extract_features_from_keypoints(pose2)
        
        if features is not None:
            features_list.append(features)
            labels_list.append(item['position'])
            count += 1
        else:
            skipped += 1
            
    logger.info(f"Processed {count} samples (Skipped {skipped} invalid/missing)")
    
    if not features_list:
        raise ValueError("No valid features extracted from annotations")
    
    # Convert to numpy arrays
    X = np.array(features_list)
    y = np.array(labels_list)
    
    # Create label mapping
    unique_positions = sorted(list(set(y)))
    label_mapping = {pos: idx for idx, pos in enumerate(unique_positions)}
    y_encoded = np.array([label_mapping[pos] for pos in y])
    
    logger.info(f"Dataset prepared: {X.shape[0]} samples, {X.shape[1]} features")
    logger.info(f"Unique positions: {len(unique_positions)}")
    logger.info(f"Position distribution:\n{pd.Series(y).value_counts()}")
    
    return X, y_encoded, label_mapping


def train_classifier(X, y, label_mapping):
    """
    Train Random Forest classifier with enhanced parameters
    """
    logger.info("Splitting dataset...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    logger.info(f"Training samples: {len(X_train)}, Test samples: {len(X_test)}")
    
    # Train Random Forest
    logger.info("Training RandomForestClassifier (Balanced, 200 trees)...")
    model = RandomForestClassifier(
        n_estimators=200,      # Increased from 100
        max_depth=30,          # Increased/Explicit
        min_samples_split=5,
        class_weight='balanced', # Crucial for 120k dataset imbalance
        random_state=42,
        n_jobs=-1,
        verbose=1
    )
    
    model.fit(X_train, y_train)
    
    # Evaluate
    logger.info("Evaluating model...")
    train_score = model.score(X_train, y_train)
    test_score = model.score(X_test, y_test)
    
    logger.info(f"Training accuracy: {train_score:.4f}")
    logger.info(f"Test accuracy:     {test_score:.4f}")
    
    # Predictions
    y_pred = model.predict(X_test)
    
    # Reverse label mapping for report
    idx_to_label = {idx: pos for pos, idx in label_mapping.items()}
    target_names = [idx_to_label[i] for i in sorted(idx_to_label.keys())]
    
    # Classification report
    report = classification_report(y_test, y_pred, target_names=target_names)
    logger.info(f"Classification Report:\n{report}")
    
    # Confusion matrix
    cm = confusion_matrix(y_test, y_pred)
    # logger.info(f"Confusion Matrix:\n{cm}")
    
    metrics = {
        'train_accuracy': train_score,
        'test_accuracy': test_score,
        'classification_report': report,
        'confusion_matrix': cm.tolist()
    }
    
    return model, metrics


def save_model(model, label_mapping, metrics, output_path='models/bjj_pose_classifier.pkl'):
    """Save trained model and metadata"""
    output_path = Path(output_path)
    output_path.parent.mkdir(exist_ok=True)
    
    # generate feature names list [kp0_x, kp0_y, ..., kp16_x, kp16_y, conf]
    feature_names = []
    for i in range(17):
        feature_names.append(f"kp{i}_x_norm")
        feature_names.append(f"kp{i}_y_norm")
    feature_names.append("avg_confidence")

    model_data = {
        'model': model,
        'label_mapping': label_mapping,
        'metrics': metrics,
        'feature_names': feature_names,
        'model_type': 'random_forest_balanced_35feat'
    }
    
    joblib.dump(model_data, output_path)
    logger.info(f"Model saved to {output_path}")
    
    # Also save label mapping as JSON for easy inspection
    mapping_path = output_path.parent / 'label_mapping.json'
    with open(mapping_path, 'w') as f:
        json.dump(label_mapping, f, indent=2)
    logger.info(f"Label mapping saved to {mapping_path}")


def main():
    parser = argparse.ArgumentParser(description='Train BJJ Pose Classifier')
    parser.add_argument('--annotations', type=str, default='annotations.json', help='Path to annotations.json')
    parser.add_argument('--output', type=str, default='models/bjj_pose_classifier.pkl', help='Output model path')
    parser.add_argument('--sample', type=int, help='Use only N samples for quick testing')
    
    args = parser.parse_args()
    
    if not Path(args.annotations).exists():
        logger.error(f"Annotations file not found: {args.annotations}")
        return
    
    logger.info(f"Loading annotations from {args.annotations}...")
    with open(args.annotations, 'r') as f:
        annotations = json.load(f)
        
    X, y, label_mapping = prepare_dataset(annotations, sample_size=args.sample)
    
    model, metrics = train_classifier(X, y, label_mapping)
    
    save_model(model, label_mapping, metrics, args.output)
    logger.info("Training complete!")


if __name__ == '__main__':
    main()
