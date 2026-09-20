from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from ultralytics import YOLO


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

DEFAULT_MODEL = str(BASE_DIR / "models" / "best.pt")

PERSON_MODEL = str(BASE_DIR / "models" / "yolo11n.pt")

SUPPORTED_MODEL_EXTENSIONS = {
    ".pt",
    ".onnx",
    ".engine",
}


# ============================================================
# DETECTION MODEL
# ============================================================

@dataclass
class VisionDetection:
    label: str
    confidence: float
    detected_object: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "confidence": self.confidence,
            "detected_object": self.detected_object,
            "metadata": self.metadata,
        }


# ============================================================
# MODEL LOADER
# ============================================================

@lru_cache(maxsize=4)
def load_model(model_path: str = DEFAULT_MODEL) -> YOLO:
    path = Path(model_path)

    if not path.is_absolute():
        path = BASE_DIR / path

    if not path.exists():
        raise FileNotFoundError(
            f"Vision model not found: {path}"
        )

    if path.suffix.lower() not in SUPPORTED_MODEL_EXTENSIONS:
        raise ValueError(
            f"Unsupported model format: {path.suffix}. "
            f"Supported formats: {sorted(SUPPORTED_MODEL_EXTENSIONS)}"
        )

    print(f"[VISION] Loading model: {path}")

    model = YOLO(str(path))

    print("[VISION] Model loaded successfully")

    return model


# ============================================================
# HELPERS
# ============================================================

def normalize_confidence(value: Any) -> float:
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return 0.0


def normalize_label(label: Any) -> str:
    if label is None:
        return ""

    return (
        str(label)
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )


def create_detection(
    label: str,
    confidence: float,
    detected_object: str,
    class_id: int | None = None,
    bounding_box: list[float] | None = None,
    model_path: str | None = None,
) -> VisionDetection:

    metadata: dict[str, Any] = {}

    if class_id is not None:
        metadata["class_id"] = class_id

    if bounding_box is not None:
        metadata["bounding_box"] = bounding_box

    if model_path:
        metadata["model"] = model_path

    return VisionDetection(
        label=normalize_label(label),
        confidence=normalize_confidence(confidence),
        detected_object=detected_object,
        metadata=metadata,
    )


# ============================================================
# OBJECT DETECTION
# ============================================================

def detect_objects_from_image(
    image: Any,
    model_path: str = DEFAULT_MODEL,
    minimum_confidence: float = 0.25,
) -> list[VisionDetection]:

    if image is None:
        raise ValueError("Image is required.")

    print("[VISION] Running PPE detection...")

    model = load_model(model_path)

    results = model.predict(
        source=image,
        conf=minimum_confidence,
        verbose=False,
    )

    detections: list[VisionDetection] = []

    for result in results:

        names = result.names or {}

        if result.boxes is None:
            continue

        for box in result.boxes:

            class_id = int(box.cls[0].item())

            confidence = float(box.conf[0].item())

            label = names.get(
                class_id,
                str(class_id),
            )

            coordinates = box.xyxy[0].tolist()

            bounding_box = [
                round(float(coordinates[0]), 2),
                round(float(coordinates[1]), 2),
                round(float(coordinates[2]), 2),
                round(float(coordinates[3]), 2),
            ]

            detections.append(
                create_detection(
                    label=label,
                    confidence=confidence,
                    detected_object=label,
                    class_id=class_id,
                    bounding_box=bounding_box,
                    model_path=str(
                        Path(model_path).resolve()
                    ),
                )
            )

    print(
        f"[VISION] Detected {len(detections)} object(s)"
    )

    return detections


def detect_objects_from_frame(
    frame: Any,
    model_path: str = DEFAULT_MODEL,
    minimum_confidence: float = 0.25,
) -> list[VisionDetection]:

    return detect_objects_from_image(
        image=frame,
        model_path=model_path,
        minimum_confidence=minimum_confidence,
    )


# ============================================================
# PERSON DETECTION
# ============================================================

def detect_persons_from_image(
    image: Any,
    model_path: str = PERSON_MODEL,
    minimum_confidence: float = 0.25,
) -> list[VisionDetection]:

    if image is None:
        raise ValueError("Image is required.")

    print("[VISION] Running person detection...")

    model = load_model(model_path)

    results = model.predict(
        source=image,
        conf=minimum_confidence,
        verbose=False,
    )

    detections: list[VisionDetection] = []

    for result in results:

        names = result.names or {}

        if result.boxes is None:
            continue

        for box in result.boxes:

            class_id = int(box.cls[0].item())

            confidence = float(box.conf[0].item())

            label = normalize_label(
                names.get(
                    class_id,
                    str(class_id),
                )
            )

            if label != "person":
                continue

            coordinates = box.xyxy[0].tolist()

            bounding_box = [
                round(float(coordinates[0]), 2),
                round(float(coordinates[1]), 2),
                round(float(coordinates[2]), 2),
                round(float(coordinates[3]), 2),
            ]

            detections.append(
                create_detection(
                    label="person",
                    confidence=confidence,
                    detected_object="person",
                    class_id=class_id,
                    bounding_box=bounding_box,
                    model_path=str(
                        Path(model_path).resolve()
                    ),
                )
            )

    print(
        f"[VISION] Detected {len(detections)} person(s)"
    )

    return detections


def detect_persons_from_frame(
    frame: Any,
    model_path: str = PERSON_MODEL,
    minimum_confidence: float = 0.25,
) -> list[VisionDetection]:

    return detect_persons_from_image(
        image=frame,
        model_path=model_path,
        minimum_confidence=minimum_confidence,
    )


# ============================================================
# FILTERING
# ============================================================

def filter_detections(
    detections: list[VisionDetection],
    labels: set[str] | None = None,
    minimum_confidence: float = 0.0,
) -> list[VisionDetection]:

    normalized_labels = {
        normalize_label(label)
        for label in labels
    } if labels else None

    filtered = []

    for detection in detections:

        if detection.confidence < minimum_confidence:
            continue

        if normalized_labels:
            if normalize_label(
                detection.label
            ) not in normalized_labels:
                continue

        filtered.append(detection)

    return filtered


# ============================================================
# CONSTRUCTION CLASSES
# ============================================================

CONSTRUCTION_LABELS = {
    "person",
    "hardhat",
    "helmet",
    "no_hardhat",
    "person_without_helmet",

    "safety_vest",
    "no_safety_vest",
    "person_without_vest",

    "gloves",
    "no_gloves",

    "safety_shoes",
    "no_boots",

    "mask",
    "no_mask",

    "barricade",
    "safety_net",

    "excavators",
    "dump_truck",
    "truck",
    "wheel_loader",
    "mini_van",
    "dumpster",
}


def is_construction_detection(
    detection: VisionDetection,
) -> bool:

    return (
        normalize_label(detection.label)
        in CONSTRUCTION_LABELS
    )


def get_safety_detections(
    detections: list[VisionDetection],
) -> list[VisionDetection]:

    return [
        detection
        for detection in detections
        if is_construction_detection(detection)
    ]


# ============================================================
# PPE VIOLATIONS
# ============================================================

PPE_VIOLATIONS = {
    "no_hardhat": "helmet_violation",
    "person_without_helmet": "helmet_violation",

    "no_safety_vest": "vest_violation",
    "person_without_vest": "vest_violation",

    "no_gloves": "gloves_violation",

    "no_boots": "boots_violation",

    "no_mask": "mask_violation",
}


def get_ppe_violations(
    detections: list[VisionDetection],
) -> list[VisionDetection]:

    violations = []

    for detection in detections:

        label = normalize_label(
            detection.label
        )

        if label in PPE_VIOLATIONS:
            violations.append(detection)

    return violations


# ============================================================
# PPE COUNTING
# ============================================================

def count_labels(
    detections: list[VisionDetection],
) -> dict[str, int]:

    counts: dict[str, int] = {}

    for detection in detections:

        label = normalize_label(
            detection.label
        )

        counts[label] = counts.get(
            label,
            0,
        ) + 1

    return counts


# ============================================================
# COMPLIANCE
# ============================================================

def calculate_compliance(
    worker_count: int,
    compliant_count: int,
) -> float:

    if worker_count <= 0:
        return 0.0

    compliant_count = max(
        0,
        min(compliant_count, worker_count),
    )

    return round(
        (compliant_count / worker_count) * 100,
        2,
    )


# ============================================================
# RISK LEVEL
# ============================================================

def calculate_risk_level(
    violation_count: int,
    worker_count: int,
    evidence_sufficient: bool,
) -> str:

    if not evidence_sufficient:
        return "UNKNOWN"

    if worker_count <= 0:
        return "UNKNOWN"

    if violation_count >= 3:
        return "CRITICAL"

    if violation_count == 2:
        return "HIGH"

    if violation_count == 1:
        return "MEDIUM"

    return "LOW"


# ============================================================
# PPE ANALYSIS
# ============================================================

def analyze_ppe_image(
    image: Any,
    model_path: str = DEFAULT_MODEL,
    minimum_confidence: float = 0.25,
) -> dict[str, Any]:

    detections = detect_objects_from_image(
        image=image,
        model_path=model_path,
        minimum_confidence=minimum_confidence,
    )

    counts = count_labels(detections)

    violations = get_ppe_violations(
        detections
    )

    worker_count = counts.get(
        "person",
        0,
    )

    hardhat_count = (
        counts.get("hardhat", 0)
        + counts.get("helmet", 0)
    )

    safety_vest_count = counts.get(
        "safety_vest",
        0,
    )

    gloves_count = counts.get(
        "gloves",
        0,
    )

    safety_shoes_count = counts.get(
        "safety_shoes",
        0,
    )

    mask_count = counts.get(
        "mask",
        0,
    )

    # --------------------------------------------------------
    # Evidence
    # --------------------------------------------------------

    evidence_sufficient = worker_count > 0

    # --------------------------------------------------------
    # Explicit violation classes
    # --------------------------------------------------------

    helmet_violations = sum(
        1
        for detection in violations
        if PPE_VIOLATIONS.get(
            normalize_label(detection.label)
        ) == "helmet_violation"
    )

    vest_violations = sum(
        1
        for detection in violations
        if PPE_VIOLATIONS.get(
            normalize_label(detection.label)
        ) == "vest_violation"
    )

    gloves_violations = sum(
        1
        for detection in violations
        if PPE_VIOLATIONS.get(
            normalize_label(detection.label)
        ) == "gloves_violation"
    )

    boots_violations = sum(
        1
        for detection in violations
        if PPE_VIOLATIONS.get(
            normalize_label(detection.label)
        ) == "boots_violation"
    )

    mask_violations = sum(
        1
        for detection in violations
        if PPE_VIOLATIONS.get(
            normalize_label(detection.label)
        ) == "mask_violation"
    )

    # --------------------------------------------------------
    # Compliance
    # --------------------------------------------------------

    if worker_count > 0:

        known_compliant_workers = max(
            0,
            worker_count
            - helmet_violations
            - vest_violations,
        )

        compliance = calculate_compliance(
            worker_count,
            known_compliant_workers,
        )

    else:
        compliance = 0.0

    # --------------------------------------------------------
    # Risk
    # --------------------------------------------------------

    risk_level = calculate_risk_level(
        violation_count=len(violations),
        worker_count=worker_count,
        evidence_sufficient=evidence_sufficient,
    )

    # --------------------------------------------------------
    # Status
    # --------------------------------------------------------

    if not evidence_sufficient:
        status = "INSUFFICIENT_EVIDENCE"

    elif len(violations) == 0:
        status = "COMPLIANT"

    else:
        status = "VIOLATION_DETECTED"

    # --------------------------------------------------------
    # Safe flag
    # --------------------------------------------------------

    safe = (
        evidence_sufficient
        and len(violations) == 0
    )

    return {
        "total_detections": len(detections),

        "worker_count": worker_count,

        "ppe_counts": {
            "hardhat": hardhat_count,
            "safety_vest": safety_vest_count,
            "gloves": gloves_count,
            "safety_shoes": safety_shoes_count,
            "mask": mask_count,
        },

        "violations": [
            {
                **violation.to_dict(),
                "violation_type": PPE_VIOLATIONS.get(
                    normalize_label(
                        violation.label
                    ),
                    "unknown",
                ),
            }
            for violation in violations
        ],

        "violation_count": len(violations),

        "violation_summary": {
            "helmet": helmet_violations,
            "vest": vest_violations,
            "gloves": gloves_violations,
            "boots": boots_violations,
            "mask": mask_violations,
        },

        "compliance_percentage": compliance,

        "risk_level": risk_level,

        "status": status,

        "safe": safe,

        "evidence_sufficient": evidence_sufficient,

        "detection_counts": counts,

        "detections": [
            detection.to_dict()
            for detection in detections
        ],
    }


# ============================================================
# GENERAL IMAGE ANALYSIS
# ============================================================

def analyze_image(
    image: Any,
    model_path: str = DEFAULT_MODEL,
    minimum_confidence: float = 0.25,
) -> list[dict[str, Any]]:

    detections = detect_objects_from_image(
        image=image,
        model_path=model_path,
        minimum_confidence=minimum_confidence,
    )

    safety_detections = get_safety_detections(
        detections
    )

    return [
        detection.to_dict()
        for detection in safety_detections
    ]