from typing import TypedDict, Optional


class InspectionState(TypedDict):
    # Identity
    inspection_id: str
    prefecture_id: str

    # Input
    image_bytes: bytes
    image_filename: str

    # Analysis output from Gemini
    damage_type: Optional[str]       # Crack | Corrosion | Spalling | Unknown
    severity_rank: Optional[str]     # A | B | C | D
    confidence: Optional[float]      # 0.0 – 1.0
    notes: Optional[str]

    # Routing decision from rule_validator
    route: Optional[str]             # normal | human_review | alert

    # Human-in-the-loop correction
    human_correction: Optional[dict]

    # Report output
    pdf_path: Optional[str]
    report_timestamp: Optional[str]

    # Alert simulation
    alert_sent: bool
    alert_message: Optional[str]
