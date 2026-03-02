"""
graph/nodes.py
LangGraph node implementations for the bridge inspection workflow.

Nodes
-----
image_analyzer        – calls Gemini VLM, populates damage fields
rule_validator        – applies business rules, sets route flag
email_alert_stub      – simulates Rank-A email alert (print + st.warning)
report_generator      – generates PDF, saves to JSON log
human_review_placeholder – saves pending record; waits for HIL correction in UI
"""
import datetime
from typing import Literal

from graph.state import InspectionState
from services.pdf_engine import generate_pdf
from services.storage import save_inspection
from services.vision_vlm import analyze_image

# ─── Allowed constants ───────────────────────────────────────────────────────

ALLOWED_DAMAGE_TYPES = {"Crack", "Corrosion", "Spalling", "Unknown"}
LOW_CONFIDENCE_THRESHOLD = 0.70


# ─── Node: image_analyzer ────────────────────────────────────────────────────

def image_analyzer(state: InspectionState) -> InspectionState:
    """
    Send image to Gemini 1.5 Flash and populate damage analysis fields.
    """
    result = analyze_image(
        image_bytes=state["image_bytes"],
        prefecture_id=state.get("prefecture_id", "JP-TYO-001"),
    )
    return {
        **state,
        "damage_type":   result.damage_type,
        "severity_rank": result.severity_rank,
        "confidence":    result.confidence,
        "notes":         result.notes,
    }


# ─── Node: rule_validator ────────────────────────────────────────────────────

def rule_validator(state: InspectionState) -> InspectionState:
    """
    Apply deterministic business rules to validated LLM output.

    Routing matrix
    ──────────────
    confidence < 0.70  OR  unknown damage type  →  human_review
    severity_rank == 'A'                         →  alert
    otherwise                                    →  normal
    """
    confidence   = state.get("confidence") or 0.0
    severity     = state.get("severity_rank", "D")
    damage_type  = state.get("damage_type", "Unknown")

    if confidence < LOW_CONFIDENCE_THRESHOLD or damage_type not in ALLOWED_DAMAGE_TYPES:
        route = "human_review"
    elif severity == "A":
        route = "alert"
    else:
        route = "normal"

    return {**state, "route": route}


# ─── Conditional edge function ───────────────────────────────────────────────

def route_decision(state: InspectionState) -> Literal["human_review", "email_alert", "report_generator"]:
    """
    Maps state.route → next node name for LangGraph conditional edges.
    """
    mapping = {
        "human_review": "human_review",
        "alert":        "email_alert",
        "normal":       "report_generator",
    }
    return mapping.get(state.get("route", "normal"), "report_generator")


# ─── Node: email_alert_stub ──────────────────────────────────────────────────

def email_alert_stub(state: InspectionState) -> InspectionState:
    """
    Simulate Rank-A critical email alert.
    Writes to stdout; Streamlit UI reads alert_message from state.
    """
    msg_lines = [
        "=" * 60,
        "[ALERT SIMULATION]  RANK A CRITICAL DAMAGE DETECTED",
        f"  Inspection ID : {state.get('inspection_id')}",
        f"  Prefecture    : {state.get('prefecture_id')}",
        f"  Damage Type   : {state.get('damage_type')}",
        f"  Confidence    : {int((state.get('confidence') or 0) * 100)} %",
        f"  Notes         : {state.get('notes', '')}",
        "  ACTION        : IMMEDIATE STRUCTURAL ENGINEER INSPECTION REQUIRED",
        "=" * 60,
    ]
    alert_message = "\n".join(msg_lines)
    print(alert_message)

    return {
        **state,
        "alert_sent":    True,
        "alert_message": alert_message,
    }


# ─── Node: report_generator ──────────────────────────────────────────────────

def report_generator(state: InspectionState) -> InspectionState:
    """
    Generate PDF report and persist inspection record to JSON log.
    """
    ts = datetime.datetime.now().isoformat()
    state_with_ts = {**state, "report_timestamp": ts}

    pdf_path = generate_pdf(state_with_ts)

    final_state = {**state_with_ts, "pdf_path": pdf_path}
    save_inspection(final_state)

    return final_state


# ─── Node: human_review_placeholder ─────────────────────────────────────────

def human_review_placeholder(state: InspectionState) -> InspectionState:
    """
    Save a pending record with route='human_review'.
    The Streamlit Human Review page handles correction and re-generation.
    """
    ts = datetime.datetime.now().isoformat()
    pending_state = {**state, "report_timestamp": ts, "pdf_path": None}
    save_inspection(pending_state)
    return pending_state
