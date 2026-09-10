from dataclasses import dataclass


# ============================================================
# HAZARD DEFINITIONS
# ============================================================

@dataclass(frozen=True)
class HazardDefinition:
    hazard_type: str
    title: str
    description: str
    severity: str
    risk_score: int


HAZARD_DEFINITIONS: dict[str, HazardDefinition] = {
    # --------------------------------------------------------
    # PPE VIOLATIONS
    # --------------------------------------------------------

    "person_without_helmet": HazardDefinition(
        hazard_type="helmet_violation",
        title="Worker detected without helmet",
        description=(
            "A worker was detected without the required "
            "protective helmet."
        ),
        severity="high",
        risk_score=85,
    ),

    "person_without_vest": HazardDefinition(
        hazard_type="no_safety_vest",
        title="Worker detected without safety vest",
        description=(
            "A worker was detected without the required "
            "high-visibility safety vest."
        ),
        severity="critical",
        risk_score=92,
    ),

    "person_without_safety_vest": HazardDefinition(
        hazard_type="no_safety_vest",
        title="Worker detected without safety vest",
        description=(
            "A worker was detected without the required "
            "high-visibility safety vest."
        ),
        severity="critical",
        risk_score=92,
    ),

    "ppe_violation": HazardDefinition(
        hazard_type="ppe_violation",
        title="PPE violation detected",
        description=(
            "A worker was detected without required "
            "personal protective equipment."
        ),
        severity="high",
        risk_score=85,
    ),

    # --------------------------------------------------------
    # FIRE / SMOKE
    # --------------------------------------------------------

    "fire": HazardDefinition(
        hazard_type="fire_hazard",
        title="Fire hazard detected",
        description=(
            "AI vision detected a potential fire hazard "
            "inside the monitored construction zone."
        ),
        severity="critical",
        risk_score=95,
    ),

    "fire_hazard": HazardDefinition(
        hazard_type="fire_hazard",
        title="Fire hazard detected",
        description=(
            "A potential fire hazard was detected "
            "inside the monitored construction zone."
        ),
        severity="critical",
        risk_score=95,
    ),

    "smoke": HazardDefinition(
        hazard_type="smoke_hazard",
        title="Smoke detected",
        description=(
            "Potential smoke was detected inside the "
            "monitored construction zone."
        ),
        severity="high",
        risk_score=90,
    ),

    "smoke_hazard": HazardDefinition(
        hazard_type="smoke_hazard",
        title="Smoke detected",
        description=(
            "Potential smoke was detected inside the "
            "monitored construction zone."
        ),
        severity="high",
        risk_score=90,
    ),

    # --------------------------------------------------------
    # RESTRICTED / HIGH-RISK ZONES
    # --------------------------------------------------------

    "restricted_zone_entry": HazardDefinition(
        hazard_type="restricted_zone_entry",
        title="Unauthorized entry into restricted zone",
        description=(
            "A person was detected inside a restricted "
            "or high-risk construction zone."
        ),
        severity="high",
        risk_score=88,
    ),

    "zone_violation": HazardDefinition(
        hazard_type="restricted_zone_entry",
        title="Restricted zone violation detected",
        description=(
            "A person was detected inside a restricted "
            "construction zone."
        ),
        severity="high",
        risk_score=88,
    ),

    "crane_zone_violation": HazardDefinition(
        hazard_type="crane_zone_violation",
        title="Person detected in crane operation zone",
        description=(
            "A person was detected inside an active crane "
            "operation area."
        ),
        severity="critical",
        risk_score=94,
    ),

    # --------------------------------------------------------
    # FALL / WORKER SAFETY
    # --------------------------------------------------------

    "fall_detected": HazardDefinition(
        hazard_type="worker_fall",
        title="Worker fall detected",
        description=(
            "AI vision detected a potential worker fall "
            "inside the monitored construction area."
        ),
        severity="critical",
        risk_score=98,
    ),

    "person_fallen": HazardDefinition(
        hazard_type="worker_fall",
        title="Worker fall detected",
        description=(
            "A potential worker fall was detected."
        ),
        severity="critical",
        risk_score=98,
    ),

    # --------------------------------------------------------
    # UNSAFE ACTIVITY
    # --------------------------------------------------------

    "unsafe_activity": HazardDefinition(
        hazard_type="unsafe_activity",
        title="Unsafe activity detected",
        description=(
            "Potentially unsafe worker activity was "
            "detected by the monitoring system."
        ),
        severity="high",
        risk_score=82,
    ),

    "unsafe_behavior": HazardDefinition(
        hazard_type="unsafe_activity",
        title="Unsafe behavior detected",
        description=(
            "Potentially unsafe behavior was detected "
            "inside the monitored area."
        ),
        severity="high",
        risk_score=82,
    ),

    # --------------------------------------------------------
    # COLLISION / EQUIPMENT
    # --------------------------------------------------------

    "vehicle_person_proximity": HazardDefinition(
        hazard_type="vehicle_person_proximity",
        title="Worker too close to moving equipment",
        description=(
            "A worker was detected dangerously close "
            "to moving construction equipment."
        ),
        severity="critical",
        risk_score=93,
    ),

    "equipment_collision": HazardDefinition(
        hazard_type="equipment_collision",
        title="Equipment collision risk detected",
        description=(
            "Potential collision risk involving construction "
            "equipment was detected."
        ),
        severity="critical",
        risk_score=94,
    ),
}


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_hazard_type(
    hazard_type: str,
) -> str:
    """
    Normalize a detected hazard/object label.
    """

    normalized = (hazard_type or "").strip().lower()

    normalized = normalized.replace("-", "_")
    normalized = normalized.replace(" ", "_")

    return normalized


# ============================================================
# HAZARD LOOKUP
# ============================================================

def get_hazard_definition(
    hazard_type: str,
) -> HazardDefinition | None:
    """
    Return the configured hazard definition.

    Returns None when the hazard type is not recognized.
    """

    normalized = normalize_hazard_type(
        hazard_type,
    )

    return HAZARD_DEFINITIONS.get(
        normalized,
    )


# ============================================================
# HAZARD CLASSIFICATION
# ============================================================

def classify_hazard(
    hazard_type: str,
) -> HazardDefinition | None:
    """
    Classify a detected object/event into a
    construction safety hazard.

    This function intentionally returns None for
    unknown detections instead of inventing a hazard.
    """

    return get_hazard_definition(
        hazard_type,
    )


# ============================================================
# RISK SCORE
# ============================================================

def calculate_risk_score(
    hazard_type: str,
    confidence: float | None = None,
) -> int:
    """
    Calculate a risk score from the configured hazard
    severity and optional AI confidence.

    The base score comes from the hazard definition.

    Confidence can slightly adjust the score:

        confidence >= 0.90
            full base risk

        confidence >= 0.75
            base risk - 3

        confidence >= 0.50
            base risk - 8

        confidence < 0.50
            base risk - 15

    The final score is always between 0 and 100.
    """

    hazard = get_hazard_definition(
        hazard_type,
    )

    if hazard is None:
        return 0

    base_score = hazard.risk_score

    if confidence is None:
        return base_score

    confidence = max(
        0.0,
        min(1.0, float(confidence)),
    )

    if confidence >= 0.90:
        adjustment = 0

    elif confidence >= 0.75:
        adjustment = -3

    elif confidence >= 0.50:
        adjustment = -8

    else:
        adjustment = -15

    score = base_score + adjustment

    return max(
        0,
        min(100, score),
    )


# ============================================================
# SEVERITY
# ============================================================

def get_severity(
    hazard_type: str,
) -> str:
    """
    Return the configured severity for a hazard.

    Unknown hazards default to low.
    """

    hazard = get_hazard_definition(
        hazard_type,
    )

    if hazard is None:
        return "low"

    return hazard.severity


# ============================================================
# COMPLETE HAZARD ANALYSIS
# ============================================================

def analyze_hazard(
    hazard_type: str,
    confidence: float | None = None,
) -> dict:
    """
    Perform complete hazard analysis.

    Returns a normalized result containing:

        hazard_type
        title
        description
        severity
        risk_score
        confidence
        recognized
    """

    normalized = normalize_hazard_type(
        hazard_type,
    )

    hazard = get_hazard_definition(
        normalized,
    )

    if hazard is None:
        return {
            "hazard_type": normalized,
            "title": "Unknown detection",
            "description": (
                "The detected object or activity could not "
                "be classified as a known construction hazard."
            ),
            "severity": "low",
            "risk_score": 0,
            "confidence": confidence,
            "recognized": False,
        }

    return {
        "hazard_type": hazard.hazard_type,
        "title": hazard.title,
        "description": hazard.description,
        "severity": hazard.severity,
        "risk_score": calculate_risk_score(
            normalized,
            confidence,
        ),
        "confidence": confidence,
        "recognized": True,
    }


# ============================================================
# HIGH-RISK CHECK
# ============================================================

def is_high_risk(
    hazard_type: str,
    confidence: float | None = None,
) -> bool:
    """
    Determine whether a detected hazard should be
    treated as high-risk.
    """

    analysis = analyze_hazard(
        hazard_type,
        confidence,
    )

    return (
        analysis["severity"] in {"high", "critical"}
        or analysis["risk_score"] >= 70
    )