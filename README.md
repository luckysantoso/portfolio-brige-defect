# 🌉 Bridge Defect Detector

**End-to-End AI-Powered Bridge Inspection System**  
An interactive prototype simulating the Japanese infrastructure inspection workflow.  
Built as a portfolio project demonstrating AI Engineering with LLM orchestration.

---

## 🏗️ Architecture

```
Upload Image
    │
    ▼
[image_analyzer]  ←── Gemini (Google AI Studio)
    │
    ▼
[rule_validator]  ←── Deterministic Python rules
    │
    ├── confidence < 0.70 OR unknown type ──→ [human_review]  →  Streamlit HIL Form
    │
    ├── severity == A ──────────────────────→ [email_alert]   →[report_generator]

    └── severity B / C / D ──────────────────────────────────→ [report_generator]
                                                                           │
                                                                      PDF + JSON log
```

## 🛠️ Tech Stack

| Layer         | Technology                                        |
| ------------- | ------------------------------------------------- |
| Orchestration | **LangGraph** (StateGraph)                        |
| Vision Engine | **Gemini**                                        |
| UI            | **Streamlit** (4-page SPA)                        |
| PDF Reporting | **ReportLab** (pixel-precise, bureaucratic style) |
| Data Storage  | JSON flat-file (`data/inspections.json`)          |
| Validation    | **Pydantic v2**                                   |

## 📁 Project Structure

```
portfolio_defect_brige/
├── app.py                   ← Streamlit UI entry point (4 pages)
├── graph/
│   ├── state.py             ← InspectionState TypedDict
│   ├── nodes.py             ← LangGraph node implementations
│   └── workflow.py          ← StateGraph builder
├── services/
│   ├── vision_vlm.py        ← Gemini 1.5 Flash wrapper + Pydantic schema
│   ├── pdf_engine.py        ← ReportLab pixel-precise PDF generator
│   └── storage.py           ← JSON persistence + CSV export
├── data/
│   └── inspections.json     ← Auto-created inspection log
├── reports/                 ← Generated PDF files (gitignored)
├── .streamlit/
│   ├── secrets.toml         ← API keys (do NOT commit)
│   └── config.toml          ← UI theme
├── requirements.txt
├── .env.example
└── README.md
```

## 🚀 Quick Start (Local)

### 1. Clone and install

```bash
git clone <your-repo-url>
cd portfolio_defect_brige

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure API key

```bash
# Option A: .streamlit/secrets.toml  (recommended)
echo 'GEMINI_API_KEY = "your_key_here"' > .streamlit/secrets.toml

# Option B: environment variable
set GEMINI_API_KEY=your_key_here      # Windows
export GEMINI_API_KEY=your_key_here   # macOS/Linux
```

Get your API key free at: https://aistudio.google.com/

### 3. Run

```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser.

## 📄 LangGraph Node Logic

### `image_analyzer`

Sends the bridge photo to **Gemini 1.5 Flash** with a structured prompt requesting:

- `damage_type`: Crack | Corrosion | Spalling | Unknown
- `severity_rank`: A (Critical) | B (Serious) | C (Minor) | D (Normal)
- `confidence`: 0.0 – 1.0
- `notes`: Technical description (max 2 sentences)

### `rule_validator`

Applies deterministic Python rules (no LLM):

```python
if confidence < 0.70 or damage_type not in ALLOWED_TYPES:
    route = "human_review"    # → Human-in-the-loop queue
elif severity_rank == "A":
    route = "alert"           # → Simulate critical email alert
else:
    route = "normal"          # → Direct to report generation
```

### `report_generator`

Generates a **pixel-precise PDF** using ReportLab in Japanese bureaucratic form style:

- Monospaced font (Courier)
- Hard grid lines
- Fixed coordinate table layout
- UUID + timestamp footer

## 📊 PDF Report Format

```
┌─────────────────────────────────────────────────────┐
│  BRIDGE INSPECTION REPORT                            │
│  Prefecture ID: JP-TYO-001    Date: 2026-03-02       │
│  Inspection No: INS-20260302-XXXXXXXX   Time: HH:MM  │
├──────────────────────┬──────────────────────────────┤
│                      │ ANALYSIS RESULTS              │
│  [BRIDGE PHOTO]      ├──────────────────────────────┤
│                      │ DAMAGE TYPE   │ Crack          │
│                      │ SEVERITY RANK │ RANK B         │
│                      │ CONFIDENCE    │ 92 %           │
│  FIG.1 PHOTOGRAPH    │ ACTION        │ SERIOUS-REPAIR │
├──────────────────────┴──────────────────────────────┤
│  SECTION 2: INSPECTION NOTES / 検査備考              │
│  [Technical notes from Gemini or human reviewer]     │
├─────────────────────────────────────────────────────┤
│  UUID: INS-...  │ CONFIDENTIAL │ Page 1 of 1         │
└─────────────────────────────────────────────────────┘
```

## ☁️ Deploy to Streamlit Cloud

1. Push this repo to GitHub (ensure `reports/` and `.streamlit/secrets.toml` are in `.gitignore`)
2. Go to https://share.streamlit.io/ → New app
3. Select repo → `app.py` as entry point
4. Add `GEMINI_API_KEY` in **Secrets** (Advanced settings)
5. Deploy ✅

## 🔑 Severity Rank Reference

| Rank | Status   | Description                          | Action                        |
| ---- | -------- | ------------------------------------ | ----------------------------- |
| A    | CRITICAL | Structural integrity compromised     | Immediate engineer inspection |
| B    | SERIOUS  | Significant structural damage        | Repair within 6 months        |
| C    | MINOR    | Minor surface damage                 | Monitoring programme          |
| D    | NORMAL   | Normal wear or no significant damage | Archive                       |

---

_Portfolio Project — Bridge Infrastructure AI Inspection Prototype_  
_Demonstrating: LangGraph orchestration · VLM integration · Pixel-precise reporting · Human-in-the-Loop_
