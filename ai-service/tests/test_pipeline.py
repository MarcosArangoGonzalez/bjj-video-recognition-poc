from app.config import Settings
from app.schemas.analysis import AnalysisResult, DetectedFrameDto
from app.services.gemini_enrichment import GeminiEnrichmentService
from app.services.pipeline import VideoAnalysisPipeline
from services.hybrid_bjj_detector import HybridBJJDetector
import numpy as np


def build_pipeline() -> VideoAnalysisPipeline:
    settings = Settings(
        yolo_model_path="./missing-model.pt",
        rf_model_path="./missing-rf.pkl",
        rf_label_mapping_path="./missing-mapping.json",
    )
    return VideoAnalysisPipeline(settings)


def test_position_labels_are_normalized():
    pipeline = build_pipeline()
    assert pipeline._normalize_position_label("turtle2") == "turtle"
    assert pipeline._normalize_position_label("side_control1") == "side_control"


def test_stabilize_positions_uses_weighted_confidence_thresholds_and_noise_penalty():
    pipeline = build_pipeline()
    frames = [
        {
            "predictedPosition": "standing",
            "positionConfidence": 0.35,
            "allTechniques": [{"type": "position", "name": "standing", "confidence": 0.35}],
        },
        {
            "predictedPosition": "standing",
            "positionConfidence": 0.36,
            "allTechniques": [{"type": "position", "name": "standing", "confidence": 0.36}],
        },
        {
            "predictedPosition": "standing",
            "positionConfidence": 0.34,
            "allTechniques": [{"type": "position", "name": "standing", "confidence": 0.34}],
        },
        {
            "predictedPosition": "mount2",
            "positionConfidence": 0.95,
            "allTechniques": [{"type": "position", "name": "mount2", "confidence": 0.95}],
        },
        {
            "predictedPosition": "side_control1",
            "positionConfidence": 0.49,
            "allTechniques": [{"type": "position", "name": "side_control1", "confidence": 0.49}],
        },
    ]
    pipeline._stabilize_positions(frames)
    assert all(frame["predictedPosition"] == "mount" for frame in frames)
    assert all(any(t["name"] == "mount" for t in frame["allTechniques"]) for frame in frames)


class _FakeModel:
    def __init__(self, probabilities):
        self._probabilities = np.array([probabilities], dtype=float)

    def predict_proba(self, _features):
        return self._probabilities


def test_local_classifier_penalizes_standing_when_technical_label_is_close():
    detector = HybridBJJDetector.__new__(HybridBJJDetector)
    detector.local_model = _FakeModel([0.62, 0.61, 0.05])
    detector.idx_to_label = {0: "standing", 1: "side_control1", 2: "unknown"}
    detector._extract_features_from_keypoints = lambda keypoints: np.zeros(35)
    result = HybridBJJDetector.predict_position_local(detector, [[0.0, 0.0, 1.0]] * 17)
    assert result["position"] == "side_control1"
    assert result["confidence"] == 0.61


def test_local_classifier_rejects_low_confidence_positions_as_unknown():
    detector = HybridBJJDetector.__new__(HybridBJJDetector)
    detector.local_model = _FakeModel([0.49, 0.30, 0.21])
    detector.idx_to_label = {0: "mount1", 1: "standing", 2: "unknown"}
    detector._extract_features_from_keypoints = lambda keypoints: np.zeros(35)
    result = HybridBJJDetector.predict_position_local(detector, [[0.0, 0.0, 1.0]] * 17)
    assert result["position"] == "unknown"


def test_kimura_geometry_does_not_require_perfect_side_control():
    detector = HybridBJJDetector.__new__(HybridBJJDetector)
    keypoints = [[0.0, 0.0, 1.0] for _ in range(17)]
    nose = [0.0, 1.0, 1.0]
    l_sh = [0.0, 0.0, 1.0]
    r_sh = [1.0, 0.0, 1.0]
    l_elb = [0.2, 0.2, 1.0]
    r_elb = [0.8, 0.2, 1.0]
    l_wr = [0.6, 0.5, 1.0]
    r_wr = [1.4, 0.5, 1.0]
    l_hip = [0.1, 0.8, 1.0]
    r_hip = [0.9, 0.8, 1.0]
    l_knee = [0.2, 1.2, 1.0]
    r_knee = [0.8, 1.2, 1.0]
    subs = HybridBJJDetector._detect_submissions(
        detector,
        keypoints,
        "unknown",
        1.0,
        nose,
        l_sh,
        r_sh,
        l_elb,
        r_elb,
        l_wr,
        r_wr,
        l_hip,
        r_hip,
        l_knee,
        r_knee,
        0.5,
        0.8,
        0.5,
        0.0,
    )
    assert any(item["name"] == "Kimura" for item in subs)


def test_filter_keeps_only_one_arm_submission_per_frame():
    detector = HybridBJJDetector.__new__(HybridBJJDetector)
    techniques = [
        {"type": "submission", "name": "Kimura", "confidence": 0.82},
        {"type": "submission", "name": "Armbar", "confidence": 0.8},
        {"type": "submission", "name": "Americana", "confidence": 0.78},
    ]
    filtered = detector._filter_techniques(techniques, "side_control")
    names = [item["name"] for item in filtered if item["type"] == "submission"]
    assert names == ["Armbar"]


def test_filter_triangle_suppresses_guillotine_and_kimura():
    detector = HybridBJJDetector.__new__(HybridBJJDetector)
    techniques = [
        {"type": "submission", "name": "Triangle Choke", "confidence": 0.88},
        {"type": "submission", "name": "Guillotine", "confidence": 0.8},
        {"type": "submission", "name": "Kimura", "confidence": 0.79},
    ]
    filtered = detector._filter_techniques(techniques, "closed_guard")
    names = [item["name"] for item in filtered if item["type"] == "submission"]
    assert names == ["Triangle Choke"]


def test_position_hysteresis_updates_immediately_in_rollback_mode():
    detector = HybridBJJDetector.__new__(HybridBJJDetector)
    detector.reset_sequence_state()
    assert detector._apply_position_hysteresis("closed_guard") == "closed_guard"
    assert detector._apply_position_hysteresis("back") == "back"


def test_mount_to_5050_is_rejected_on_low_confidence():
    detector = HybridBJJDetector.__new__(HybridBJJDetector)
    detector.reset_sequence_state()
    detector.last_stable_position = "mount"
    detector._position_history_instance = ["mount", "mount"]
    detector._last_hip_height = 100.0
    keypoints = [[0.0, 0.0, 1.0] for _ in range(17)]
    keypoints[0] = [0.0, 0.0, 1.0]
    keypoints[5] = [0.0, 0.0, 1.0]
    keypoints[6] = [1.0, 0.0, 1.0]
    keypoints[11] = [0.0, 1.0, 1.0]
    keypoints[12] = [1.0, 1.0, 1.0]
    keypoints[13] = [0.1, 1.5, 1.0]
    keypoints[14] = [0.9, 1.5, 1.0]
    keypoints[15] = [0.1, 2.0, 1.0]
    keypoints[16] = [0.9, 2.0, 1.0]
    anchored = detector._apply_position_anchor("50/50_guard", 0.72, keypoints)
    assert anchored == "mount"


def test_hysteresis_keeps_detected_class_until_15_frames():
    pipeline = build_pipeline()
    frames = [
        DetectedFrameDto(frame_index=i, timestamp_seconds=float(i), detected_class="mount", confidence=0.9)
        for i in range(3)
    ] + [
        DetectedFrameDto(frame_index=3 + i, timestamp_seconds=float(3 + i), detected_class="kimura", confidence=0.9)
        for i in range(14)
    ]
    pipeline._apply_detected_class_hysteresis(frames, auto_tag=False)
    assert all(frame.detected_class == "mount" for frame in frames[1:])


def test_story_block_winner_take_all_submissions_by_accumulated_confidence():
    story = VideoAnalysisPipeline._build_final_story(
        [
            {
                "timestampSeconds": 0.0,
                "predictedPosition": "closed_guard1",
                "positionConfidence": 0.82,
                "allTechniques": [
                    {"type": "submission", "name": "Kimura", "confidence": 0.70},
                    {"type": "submission", "name": "Armbar", "confidence": 0.81},
                ],
            },
            {
                "timestampSeconds": 1.0,
                "predictedPosition": "closed_guard1",
                "positionConfidence": 0.84,
                "allTechniques": [
                    {"type": "submission", "name": "Kimura", "confidence": 0.71},
                    {"type": "submission", "name": "Armbar", "confidence": 0.80},
                ],
            },
        ]
    )
    submissions = [item for item in story if item["category"] == "SUBMISSION"]
    assert len(submissions) == 1
    assert submissions[0]["technique"] == "armbar"


def test_story_block_allows_double_threat_only_for_high_conf_triangle_armbar():
    story = VideoAnalysisPipeline._build_final_story(
        [
            {
                "timestampSeconds": 0.0,
                "predictedPosition": "closed_guard1",
                "positionConfidence": 0.9,
                "allTechniques": [
                    {"type": "submission", "name": "Triangle Choke", "confidence": 0.91},
                    {"type": "submission", "name": "Armbar", "confidence": 0.86},
                ],
            }
        ]
    )
    submissions = {item["technique"] for item in story if item["category"] == "SUBMISSION"}
    assert submissions == {"triangle_choke", "armbar"}


def test_story_block_triangle_suppresses_guillotine_and_kimura():
    story = VideoAnalysisPipeline._build_final_story(
        [
            {
                "timestampSeconds": 0.0,
                "predictedPosition": "closed_guard1",
                "positionConfidence": 0.9,
                "allTechniques": [
                    {"type": "submission", "name": "Triangle Choke", "confidence": 0.88},
                    {"type": "submission", "name": "Guillotine", "confidence": 0.84},
                    {"type": "submission", "name": "Kimura", "confidence": 0.83},
                ],
            }
        ]
    )
    submissions = {item["technique"] for item in story if item["category"] == "SUBMISSION"}
    assert submissions == {"triangle_choke"}


def test_select_primary_detection_ignores_low_confidence_techniques():
    pipeline = build_pipeline()
    label, confidence = pipeline._select_primary_detection(
        {
            "predictedPosition": "closed_guard",
            "positionConfidence": 0.72,
            "allTechniques": [{"type": "submission", "name": "Kimura", "confidence": 0.55}],
        }
    )
    assert label == "closed_guard"
    assert confidence == 0.72


def test_select_primary_detection_prefers_best_technique():
    pipeline = build_pipeline()
    label, confidence = pipeline._select_primary_detection(
        {
            "predictedPosition": "side_control",
            "positionConfidence": 0.6,
            "allTechniques": [
                {"type": "submission", "name": "Kimura", "confidence": 0.85},
                {"type": "submission", "name": "Armbar", "confidence": 0.8},
            ],
        }
    )
    assert label == "kimura"
    assert confidence == 0.85


def test_build_final_story_keeps_unique_best_entries():
    story = VideoAnalysisPipeline._build_final_story(
        [
            {
                "timestampSeconds": 0.0,
                "predictedPosition": "side_control1",
                "positionConfidence": 0.7,
                "allTechniques": [{"type": "submission", "name": "Kimura", "confidence": 0.85}],
            },
            {
                "timestampSeconds": 1.0,
                "predictedPosition": "side_control2",
                "positionConfidence": 0.75,
                "allTechniques": [{"type": "submission", "name": "Kimura", "confidence": 0.8}],
            },
        ]
    )
    assert any(block["category"] == "POSITION" and block["technique"] == "side_control" for block in story)
    assert any(block["category"] == "SUBMISSION" and block["technique"] == "kimura" for block in story)
    assert len([block for block in story if block["category"] == "SUBMISSION"]) == 1


def test_build_final_story_keeps_multiple_unique_local_candidates_in_parity_mode():
    story = VideoAnalysisPipeline._build_final_story(
        [
            {
                "timestampSeconds": 0.0,
                "predictedPosition": "closed_guard1",
                "positionConfidence": 0.92,
                "allTechniques": [{"type": "submission", "name": "Armbar", "confidence": 0.85}],
            },
            {
                "timestampSeconds": 15.0,
                "predictedPosition": "closed_guard2",
                "positionConfidence": 0.9,
                "allTechniques": [{"type": "submission", "name": "Rear Naked Choke", "confidence": 0.85}],
            },
            {
                "timestampSeconds": 36.0,
                "predictedPosition": "closed_guard2",
                "positionConfidence": 0.88,
                "allTechniques": [{"type": "submission", "name": "Triangle Choke", "confidence": 0.75}],
            },
            {
                "timestampSeconds": 44.0,
                "predictedPosition": "side_control1",
                "positionConfidence": 0.78,
                "allTechniques": [{"type": "transition", "name": "Guard Pass To Side Control", "confidence": 0.85}],
            },
        ]
    )
    assert len(story) == 8
    assert any(block["category"] == "POSITION" and block["technique"] == "closed_guard" for block in story)
    assert any(block["category"] == "POSITION" and block["technique"] == "side_control" for block in story)
    assert any(block["category"] == "SUBMISSION" and block["technique"] == "armbar" for block in story)
    assert any(block["category"] == "SUBMISSION" and block["technique"] == "triangle_choke" for block in story)
    assert any(block["category"] == "TRANSITION" and block["technique"] == "guard_pass_to_side_control" for block in story)


def test_parity_mode_preserves_observed_position_without_contextual_inference():
    story = VideoAnalysisPipeline._build_final_story(
        [
            {
                "timestampSeconds": 0.0,
                "predictedPosition": "turtle2",
                "positionConfidence": 0.3,
                "allTechniques": [{"type": "submission", "name": "Kimura", "confidence": 0.85}],
            }
        ]
    )
    submission = [block for block in story if block["category"] == "SUBMISSION"][0]
    assert submission["technique"] == "kimura"
    assert not any(block["category"] == "POSITION" for block in story)


def test_primary_class_prefers_submission_story():
    pipeline = build_pipeline()
    story = [
        {"category": "POSITION", "technique": "mount", "confidence": 92},
        {"category": "SUBMISSION", "technique": "armbar", "confidence": 80},
    ]
    assert pipeline._compute_primary_class(story, []) == "armbar"


def test_hybrid_filter_prefers_guard_submissions_and_blocks_takedown_from_guard():
    detector = HybridBJJDetector.__new__(HybridBJJDetector)
    techniques = [
        {"type": "submission", "name": "Rear Naked Choke", "confidence": 0.85},
        {"type": "submission", "name": "Guillotine", "confidence": 0.75},
        {"type": "takedown", "name": "Takedown", "confidence": 0.85},
    ]
    filtered = detector._filter_techniques(techniques, "closed_guard")
    names = {item["name"] for item in filtered}
    assert "Guillotine" in names
    assert "Rear Naked Choke" not in names
    assert "Takedown" not in names


def test_gemini_merge_does_not_add_new_labels():
    service = GeminiEnrichmentService(Settings())
    base = AnalysisResult(
        publication_id=1,
        status="completed",
        frames=[DetectedFrameDto(frame_index=10, timestamp_seconds=1.0, detected_class="kimura", confidence=0.85, feedback="local")],
        combat_story=[
            {
                "category": "SUBMISSION",
                "technique": "kimura",
                "label": "Kimura",
                "status": "Secured",
                "description": "local",
                "visuals": [],
                "confidence": 85,
                "start_timestamp": 1.0,
                "duration": 1.0,
            }
        ],
        primary_detected_class="kimura",
    )
    enriched = service._replace_summary_with_gemini(
        base,
        [
            {
                "category": "SUBMISSION",
                "label": "Armbar",
                "status": "Completed",
                "timestamp_seconds": 1.0,
                "confidence": 0.98,
                "detail": "hallucinated replacement",
                "observed_mechanics": [],
            }
        ],
    )
    submissions = [block for block in enriched.combat_story if block["category"] == "SUBMISSION"]
    assert len(submissions) == 1
    assert submissions[0]["technique"] == "armbar"


def test_gemini_summary_can_infer_contextual_position():
    service = GeminiEnrichmentService(Settings())
    base = AnalysisResult(
        publication_id=1,
        status="completed",
        frames=[DetectedFrameDto(frame_index=10, timestamp_seconds=1.0, detected_class="kimura", confidence=0.85, feedback="local")],
        combat_story=[],
        primary_detected_class="kimura",
    )
    enriched = service._replace_summary_with_gemini(
        base,
        [
            {
                "category": "SUBMISSION",
                "label": "Kimura",
                "status": "Completed",
                "timestamp_seconds": 1.0,
                "confidence": 0.97,
                "detail": "Figure-four grip fully locked with shoulder rotation visible.",
                "observed_mechanics": ["Figure-four grip", "Shoulder isolated"],
            }
        ],
    )
    position = [block for block in enriched.combat_story if block["category"] == "POSITION"][0]
    submission = [block for block in enriched.combat_story if block["category"] == "SUBMISSION"][0]
    assert submission["technique"] == "kimura"
    assert position["technique"] == "side_control"


def test_gemini_hallucination_filter_removes_triangle_when_takedown_exists():
    service = GeminiEnrichmentService(Settings())
    detections = [
        {"category": "TAKEDOWN", "label": "Takedown", "confidence": 0.9},
        {"category": "SUBMISSION", "label": "Triangle Choke", "confidence": 0.9},
    ]
    filtered = service._filter_biomechanical_hallucinations(detections)
    labels = {service._normalize_label(str(item["label"])) for item in filtered}
    assert "takedown" in labels
    assert "triangle_choke" not in labels


def test_gemini_filter_by_local_support_rejects_unseen_labels():
    service = GeminiEnrichmentService(Settings())
    base = AnalysisResult(
        publication_id=1,
        status="completed",
        frames=[
            DetectedFrameDto(frame_index=0, timestamp_seconds=0.0, detected_class="kimura", confidence=0.85),
            DetectedFrameDto(frame_index=1, timestamp_seconds=1.0, detected_class="side_control", confidence=0.6),
        ],
        combat_story=[
            {
                "category": "POSITION",
                "technique": "side_control",
                "label": "Side Control",
                "status": "Secured",
                "description": "local",
                "visuals": [],
                "confidence": 60,
                "start_timestamp": 0.0,
                "duration": 1.0,
            },
            {
                "category": "SUBMISSION",
                "technique": "kimura",
                "label": "Kimura",
                "status": "Attempted",
                "description": "local",
                "visuals": [],
                "confidence": 85,
                "start_timestamp": 0.0,
                "duration": 1.0,
            },
        ],
        primary_detected_class="kimura",
    )
    filtered = service._filter_by_local_support(
        base,
        [
            {"category": "SUBMISSION", "label": "Guillotine", "confidence": 0.9},
            {"category": "SUBMISSION", "label": "Kimura", "confidence": 0.9},
            {"category": "POSITION", "label": "Side Control", "confidence": 0.9},
        ],
    )
    labels = {service._normalize_label(str(item["label"])) for item in filtered}
    assert "kimura" in labels
    assert "side_control" in labels
    assert "guillotine" not in labels
