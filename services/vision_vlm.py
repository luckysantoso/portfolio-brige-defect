"""
services/vision_vlm.py
Wrapper around Gemini 2.0 Flash for bridge damage visual analysis.
Uses the new google-genai SDK (google.generativeai is deprecated).
"""
import io
import json
import os

from google import genai
from google.genai import types
from PIL import Image
from pydantic import BaseModel, Field, field_validator

# ─── Pydantic schema ────────────────────────────────────────────────────────

ALLOWED_TYPES = {"Crack", "Corrosion", "Spalling", "Unknown"}
ALLOWED_RANKS = {"A", "B", "C", "D"}


class DamageAnalysis(BaseModel):
    damage_type: str = Field(..., description="Crack | Corrosion | Spalling | Unknown")
    severity_rank: str = Field(..., description="A | B | C | D")
    confidence: float = Field(..., ge=0.0, le=1.0)
    notes: str = Field(default="", description="Brief technical description")

    @field_validator("damage_type")
    @classmethod
    def validate_damage_type(cls, v: str) -> str:
        return v if v in ALLOWED_TYPES else "Unknown"

    @field_validator("severity_rank")
    @classmethod
    def validate_severity_rank(cls, v: str) -> str:
        v_upper = v.upper()
        return v_upper if v_upper in ALLOWED_RANKS else "D"

    @field_validator("confidence")
    @classmethod
    def normalize_confidence(cls, v: float) -> float:
        # Model sometimes returns 0-100 instead of 0-1
        return v / 100.0 if v > 1.0 else v


# ─── Prompt ─────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert structural civil engineer specialising in Japanese bridge inspection.

Analyse the provided bridge photograph and return ONLY a valid JSON object — no markdown, no explanation.

Required fields:
  - "damage_type"   : one of "Crack", "Corrosion", "Spalling", "Unknown"
  - "severity_rank" : one of "A" (Critical/Immediate), "B" (Serious/Repair Required),
                              "C" (Minor/Monitor), "D" (Normal/Archive)
  - "confidence"    : float between 0.0 and 1.0
  - "notes"         : max 2 sentences describing the damage location and pattern

Severity criteria:
  A – Structural integrity compromised; immediate intervention required
  B – Significant damage; repair required within 6 months
  C – Minor damage; monitoring programme recommended
  D – Normal wear or no significant damage detected

Example response:
{"damage_type":"Crack","severity_rank":"B","confidence":0.92,"notes":"Longitudinal crack along expansion joint. Estimated width 2 mm."}
"""


# ─── API helper ─────────────────────────────────────────────────────────────

def _get_api_key() -> str:
    """Read API key from env or Streamlit secrets."""
    key = os.environ.get("GEMINI_API_KEY", "")
    if key:
        return key
    try:
        import streamlit as st  # type: ignore
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        raise ValueError(
            "GEMINI_API_KEY not found. "
            "Set it in .env or .streamlit/secrets.toml"
        )


def _get_client() -> genai.Client:
    """Create an authenticated google.genai Client."""
    return genai.Client(api_key=_get_api_key())


def _parse_gemini_response(raw: str) -> dict:
    """Strip markdown fences and parse JSON."""
    text = raw.strip()
    if text.startswith("```"):
        # Remove opening fence
        text = text.split("```", 1)[1]
        if text.startswith("json"):
            text = text[4:]
        # Remove closing fence
        if "```" in text:
            text = text.rsplit("```", 1)[0]
    return json.loads(text.strip())


# ─── Model priority list (tried in order until one succeeds) ─────────────────

CANDIDATE_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-flash-latest",
    "gemini-2.0-flash-lite",
]


# ─── Public API ─────────────────────────────────────────────────────────────

def analyze_image(image_bytes: bytes, prefecture_id: str = "JP-TYO-001") -> DamageAnalysis:
    """
    Send an image to Gemini 2.0 Flash and return a validated DamageAnalysis.

    Args:
        image_bytes: Raw bytes of the uploaded image.
        prefecture_id: Bridge location identifier for context.

    Returns:
        DamageAnalysis Pydantic model.
    """
    client = _get_client()

    client = _get_client()

    # Normalise image to bytes with explicit MIME type
    img = Image.open(io.BytesIO(image_bytes))
    img_buf = io.BytesIO()
    fmt = img.format if img.format else "JPEG"
    img.save(img_buf, format=fmt)
    img_bytes_clean = img_buf.getvalue()
    mime = "image/jpeg" if fmt.upper() in ("JPEG", "JPG") else f"image/{fmt.lower()}"

    context_note = (
        f"Bridge location: Prefecture {prefecture_id}. "
        "Focus on structural defects visible in the photograph."
    )
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=SYSTEM_PROMPT),
                types.Part.from_text(text=context_note),
                types.Part.from_bytes(data=img_bytes_clean, mime_type=mime),
            ],
        )
    ]

    last_exc: Exception | None = None
    for model_name in CANDIDATE_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
            )
            raw_text = response.text
            data = _parse_gemini_response(raw_text)
            return DamageAnalysis(**data)
        except Exception as exc:
            last_exc = exc
            # If it's a quota/rate-limit issue try next model; otherwise raise
            err_str = str(exc)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "404" in err_str:
                continue
            raise

    raise RuntimeError(
        f"All candidate models exhausted. Last error: {last_exc}"
    )
