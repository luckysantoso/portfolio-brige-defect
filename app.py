"""
app.py
Streamlit UI for the Bridge Defect Detector prototype.

Pages
─────
🔍 Inspect        – Upload photo → run LangGraph analysis
👤 Human Review   – Correct low-confidence detections
📄 Report         – Preview & download generated PDFs
📊 History        – Full inspection log with filters & CSV export
"""
import base64
import datetime
import os
import uuid

import pandas as pd
import streamlit as st

# ─── Page config (must be first Streamlit call) ──────────────────────────────

st.set_page_config(
    page_title="Bridge Defect Detector",
    page_icon="🌉",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Lazy imports (avoid import errors before env is configured) ──────────────

from graph.state import InspectionState  # noqa: E402
from graph.workflow import build_graph  # noqa: E402
from services.pdf_engine import generate_pdf  # noqa: E402
from services.storage import export_csv, load_all_inspections, save_inspection  # noqa: E402

# ─── Constants ───────────────────────────────────────────────────────────────

SEVERITY_EMOJI = {"A": "🔴", "B": "🟠", "C": "🟡", "D": "🟢"}
SEVERITY_LABEL = {
    "A": "RANK A — CRITICAL",
    "B": "RANK B — REPAIR REQUIRED",
    "C": "RANK C — MONITOR",
    "D": "RANK D — NORMAL",
}
PAGES = ["🔍 Inspect", "👤 Human Review", "📄 Report", "📊 History"]

# ─── Page state init ─────────────────────────────────────────────────────────

if "page" not in st.session_state:
    st.session_state["page"] = PAGES[0]


# ─── Cached resources ─────────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def get_graph():
    return build_graph()


# ─── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("Bridge Defect Detector")
    st.caption("AI-Powered Bridge Inspection System")
    st.markdown("**Prefecture:** JP-TYO-001")
    st.divider()

    for _p in PAGES:
        _active = st.session_state["page"] == _p
        if st.button(
            _p,
            use_container_width=True,
            type="primary" if _active else "secondary",
            key=f"nav_{_p}",
        ):
            st.session_state["page"] = _p
            st.rerun()

    page = st.session_state["page"]

    st.divider()
    st.caption("Powered by Gemini + LangGraph")
    st.caption("© 2026 — Portfolio Project")

    # Quick stats in sidebar
    all_records = load_all_inspections()
    total        = len(all_records)
    critical     = sum(1 for r in all_records if r.get("severity_rank") == "A")
    pending_hil  = sum(1 for r in all_records
                       if r.get("route") == "human_review" and not r.get("pdf_path"))
    st.divider()
    st.metric("Total Inspections", total)
    col_a, col_b = st.columns(2)
    col_a.metric("🔴 Critical", critical)
    col_b.metric("👤 Pending", pending_hil)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — INSPECT
# ══════════════════════════════════════════════════════════════════════════════

if page == "🔍 Inspect":
    st.header("🔍 Bridge Inspection")
    st.markdown(
        "Upload a bridge photograph to run automated structural damage analysis "
        "using **Gemini** orchestrated by **LangGraph**."
    )

    left, right = st.columns([1, 1], gap="large")

    with left:
        prefecture_id = st.text_input(
            "Prefecture ID",
            value="JP-TYO-001",
            help="Japanese prefecture bridge identifier",
        )
        uploaded = st.file_uploader(
            "Upload Bridge Photo",
            type=["jpg", "jpeg", "png", "webp"],
            help="Max 10 MB — JPG / PNG / WebP",
        )

        if uploaded:
            st.image(
                uploaded,
                caption=f"📷 {uploaded.name}",
                use_container_width=True,
            )

    with right:
        if not uploaded:
            st.info("← Upload a bridge photo to get started.")
        else:
            st.subheader("Run Analysis")
            st.markdown(
                "The system will:\n"
                "1. Analyse the image with Gemini 1.5 Flash\n"
                "2. Validate result with deterministic rules\n"
                "3. Route to alert / human review / report based on severity"
            )

            if st.button("▶ Start Inspection", type="primary", use_container_width=True):
                inspection_id = (
                    f"INS-{datetime.datetime.now().strftime('%Y%m%d')}"
                    f"-{str(uuid.uuid4())[:8].upper()}"
                )
                image_bytes = uploaded.getvalue()

                initial_state: InspectionState = {
                    "inspection_id":   inspection_id,
                    "prefecture_id":   prefecture_id,
                    "image_bytes":     image_bytes,
                    "image_filename":  uploaded.name,
                    "damage_type":     None,
                    "severity_rank":   None,
                    "confidence":      None,
                    "notes":           None,
                    "route":           None,
                    "human_correction": None,
                    "pdf_path":        None,
                    "report_timestamp": None,
                    "alert_sent":      False,
                    "alert_message":   None,
                }

                with st.spinner("🔍 Analysing with Gemini…"):
                    try:
                        graph = get_graph()
                        result = graph.invoke(initial_state)
                        st.session_state["last_result"] = result
                        st.session_state["last_id"] = inspection_id
                        st.success("✅ Analysis complete!")
                    except Exception as exc:
                        st.error(f"❌ Error: {exc}")
                        st.stop()

            # ── Results panel ─────────────────────────────────────────────
            if "last_result" in st.session_state and "last_id" in st.session_state:
                result = st.session_state["last_result"]
                rank   = result.get("severity_rank", "?")
                conf   = result.get("confidence") or 0.0
                route  = result.get("route", "normal")

                st.divider()
                st.subheader("📊 Analysis Results")

                # Status banners
                if rank == "A":
                    st.error("🚨 CRITICAL DAMAGE — IMMEDIATE ACTION REQUIRED")
                    if result.get("alert_sent"):
                        with st.expander("⚠️ Alert simulation details"):
                            st.code(result.get("alert_message", ""), language="text")
                elif route == "human_review":
                    st.warning(
                        "⚠️ Confidence below 70 % or unknown damage type — "
                        "queued for Human Review."
                    )
                elif rank == "B":
                    st.warning("🟠 SERIOUS damage detected — repair required.")
                elif rank == "C":
                    st.info("🟡 Minor damage detected — monitoring recommended.")
                else:
                    st.success("🟢 No significant structural damage detected.")

                # Metrics
                m1, m2, m3 = st.columns(3)
                m1.metric("Damage Type",  result.get("damage_type", "N/A"))
                m2.metric(
                    "Severity",
                    f"{SEVERITY_EMOJI.get(rank, '⚪')} "
                    f"{SEVERITY_LABEL.get(rank, rank)}",
                )
                m3.metric("Confidence", f"{int(conf * 100)} %")

                st.info(f"**Inspector Notes:** {result.get('notes', '—')}")
                st.caption(f"Inspection ID: `{result.get('inspection_id')}`")

                # Download PDF
                pdf_path = result.get("pdf_path")
                if pdf_path and os.path.exists(pdf_path):
                    with open(pdf_path, "rb") as f:
                        st.download_button(
                            "📥 Download PDF Report",
                            data=f.read(),
                            file_name=os.path.basename(pdf_path),
                            mime="application/pdf",
                            type="primary",
                            use_container_width=True,
                        )
                elif route == "human_review":
                    st.info(
                        "👤 Added to **Human Review** queue. "
                        "Go to the Human Review page to verify and generate a report."
                    )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — HUMAN REVIEW
# ══════════════════════════════════════════════════════════════════════════════

elif page == "👤 Human Review":
    st.header("👤 Human Review Queue")
    st.markdown(
        "Inspections flagged due to **low confidence (< 70 %)** or **unknown damage type**. "
        "Correct the classification and generate the final report."
    )

    all_records = load_all_inspections()
    pending = [
        r for r in all_records
        if r.get("route") == "human_review" and not r.get("pdf_path")
    ]

    if not pending:
        st.success("✅ No inspections pending human review.")
    else:
        st.warning(f"⚠️ {len(pending)} inspection(s) awaiting human review.")

        for record in pending:
            iid = record["inspection_id"]
            with st.expander(
                f"📋 {iid}  —  "
                f"Auto-detected: {record.get('damage_type', 'Unknown')}  |  "
                f"Confidence: {int((record.get('confidence') or 0) * 100)} %",
                expanded=True,
            ):
                info_col, form_col = st.columns([1, 1], gap="large")

                with info_col:
                    st.markdown("**Auto-Detection Results**")
                    st.write(f"**Prefecture  :** {record.get('prefecture_id')}")
                    st.write(f"**Damage Type :** {record.get('damage_type', 'N/A')}")
                    st.write(f"**Severity    :** {record.get('severity_rank', 'N/A')}")
                    st.write(f"**Confidence  :** {int((record.get('confidence') or 0) * 100)} %")
                    st.write(f"**Notes       :** {record.get('notes', '—')}")
                    st.write(f"**Timestamp   :** {(record.get('report_timestamp') or '')[:19]}")

                with form_col:
                    st.markdown("**Human Correction Form**")
                    with st.form(key=f"hil_{iid}"):
                        corr_type = st.selectbox(
                            "Corrected Damage Type",
                            ["Crack", "Corrosion", "Spalling", "Unknown"],
                            index=0,
                            key=f"ct_{iid}",
                        )
                        corr_rank = st.selectbox(
                            "Corrected Severity Rank",
                            ["A", "B", "C", "D"],
                            index=1,
                            key=f"cr_{iid}",
                        )
                        corr_notes = st.text_area(
                            "Technical Notes",
                            value=record.get("notes", ""),
                            height=100,
                            key=f"cn_{iid}",
                        )
                        submitted = st.form_submit_button(
                            "✅ Submit Correction & Generate Report",
                            type="primary",
                            use_container_width=True,
                        )

                    if submitted:
                        updated = {
                            **record,
                            "damage_type":      corr_type,
                            "severity_rank":    corr_rank,
                            "notes":            corr_notes,
                            "route":            "normal",
                            "human_correction": {
                                "corrected_by": "human_reviewer",
                                "at": datetime.datetime.now().isoformat(),
                            },
                        }

                        # Rank A after human correction → also simulate alert
                        if corr_rank == "A":
                            alert_msg = (
                                f"[ALERT SIMULATION – HUMAN REVIEW]  "
                                f"Rank A confirmed by reviewer.\n"
                                f"Inspection: {iid}\n"
                                f"Prefecture: {record.get('prefecture_id')}"
                            )
                            updated["alert_sent"]    = True
                            updated["alert_message"] = alert_msg
                            st.error("🚨 Rank A confirmed — alert simulation triggered.")

                        with st.spinner("Generating corrected report …"):
                            pdf_path = generate_pdf(updated)
                            updated["pdf_path"]          = pdf_path
                            updated["report_timestamp"]  = datetime.datetime.now().isoformat()
                            save_inspection(updated)

                        st.success(f"✅ Report generated: `{os.path.basename(pdf_path)}`")
                        if os.path.exists(pdf_path):
                            with open(pdf_path, "rb") as pdf_file:
                                st.download_button(
                                    "📥 Download Corrected Report",
                                    data=pdf_file.read(),
                                    file_name=os.path.basename(pdf_path),
                                    mime="application/pdf",
                                    key=f"dl_{iid}",
                                )
                        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — REPORT
# ══════════════════════════════════════════════════════════════════════════════

elif page == "📄 Report":
    st.header("📄 Report Viewer")
    st.markdown("Preview and download generated inspection PDF reports.")

    all_records = load_all_inspections()
    reported = [
        r for r in all_records
        if r.get("pdf_path") and os.path.exists(r.get("pdf_path", ""))
    ]

    if not reported:
        st.info("No reports generated yet. Go to the **Inspect** page to analyse a bridge.")
    else:
        options = [r["inspection_id"] for r in reported]

        def fmt_option(x: str) -> str:
            rec = next((r for r in reported if r["inspection_id"] == x), {})
            rank = rec.get("severity_rank", "?")
            return (
                f"{x}  —  {rec.get('damage_type', '?')}  |  "
                f"{SEVERITY_EMOJI.get(rank, '⚪')} Rank {rank}  |  "
                f"{(rec.get('report_timestamp') or '')[:10]}"
            )

        selected_id = st.selectbox(
            "Select Inspection Report",
            options=options,
            format_func=fmt_option,
        )

        record = next(r for r in reported if r["inspection_id"] == selected_id)

        preview_col, meta_col = st.columns([2, 1], gap="large")

        with preview_col:
            st.subheader("PDF Preview")
            with open(record["pdf_path"], "rb") as f:
                pdf_bytes = f.read()
            b64 = base64.b64encode(pdf_bytes).decode()
            st.markdown(
                f'<iframe src="data:application/pdf;base64,{b64}" '
                f'width="100%" height="640px" type="application/pdf">'
                f'<p>Your browser does not support inline PDF preview. '
                f'<a href="data:application/pdf;base64,{b64}" download>Download PDF</a></p>'
                f'</iframe>',
                unsafe_allow_html=True,
            )

        with meta_col:
            st.subheader("Report Summary")
            rank = record.get("severity_rank", "?")
            conf = record.get("confidence") or 0.0

            st.metric("Damage Type", record.get("damage_type", "N/A"))
            st.metric(
                "Severity",
                f"{SEVERITY_EMOJI.get(rank, '⚪')} Rank {rank}",
            )
            st.metric("Confidence", f"{int(conf * 100)} %")

            st.divider()
            st.write(f"**Prefecture :** {record.get('prefecture_id', 'N/A')}")
            st.write(f"**Timestamp  :** {(record.get('report_timestamp') or '')[:19]}")
            st.write(f"**Route      :** {record.get('route', 'N/A')}")

            if record.get("human_correction"):
                st.info("✏️ Human-corrected classification applied.")
                corr = record["human_correction"]
                st.caption(f"Corrected at: {str(corr.get('at', ''))[:19]}")

            if record.get("alert_sent"):
                st.error("🚨 Critical alert was issued for this inspection.")

            st.divider()
            with open(record["pdf_path"], "rb") as f:
                st.download_button(
                    "📥 Download PDF",
                    data=f.read(),
                    file_name=os.path.basename(record["pdf_path"]),
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True,
                )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — HISTORY
# ══════════════════════════════════════════════════════════════════════════════

elif page == "📊 History":
    st.header("📊 Inspection History")
    st.markdown("Full log of all inspections with filtering, statistics and CSV export.")

    all_records = load_all_inspections()

    if not all_records:
        st.info("No inspection history yet. Go to the **Inspect** page to analyse your first bridge.")
    else:
        # ── Filters ───────────────────────────────────────────────────────
        f1, f2, f3 = st.columns(3)
        with f1:
            filter_rank = st.multiselect(
                "Severity Rank",
                ["A", "B", "C", "D"],
                default=["A", "B", "C", "D"],
            )
        with f2:
            filter_route = st.multiselect(
                "Route",
                ["alert", "normal", "human_review"],
                default=["alert", "normal", "human_review"],
            )
        with f3:
            filter_pdf = st.selectbox(
                "Report Status",
                ["All", "Has PDF", "No PDF"],
                index=0,
            )

        filtered = [
            r for r in all_records
            if r.get("severity_rank") in filter_rank
            and r.get("route") in filter_route
        ]
        if filter_pdf == "Has PDF":
            filtered = [r for r in filtered if r.get("pdf_path")]
        elif filter_pdf == "No PDF":
            filtered = [r for r in filtered if not r.get("pdf_path")]

        # ── Summary metrics ───────────────────────────────────────────────
        st.divider()
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total",             len(all_records))
        c2.metric("🔴 Critical (A)",    sum(1 for r in all_records if r.get("severity_rank") == "A"))
        c3.metric("🟠 Serious (B)",     sum(1 for r in all_records if r.get("severity_rank") == "B"))
        c4.metric("👤 Pending Review",  sum(1 for r in all_records
                                           if r.get("route") == "human_review"
                                           and not r.get("pdf_path")))
        c5.metric("📄 Reports Ready",   sum(1 for r in all_records if r.get("pdf_path")))

        # ── Data table ────────────────────────────────────────────────────
        st.divider()
        st.subheader(f"Records  ({len(filtered)} shown)")

        if not filtered:
            st.info("No records match the selected filters.")
        else:
            df_rows = [
                {
                    "ID":          r.get("inspection_id", ""),
                    "Prefecture":  r.get("prefecture_id", ""),
                    "Damage Type": r.get("damage_type", ""),
                    "Rank":        f"{SEVERITY_EMOJI.get(r.get('severity_rank', ''), '⚪')} "
                                   f"{r.get('severity_rank', '')}",
                    "Conf %":      int((r.get("confidence") or 0) * 100),
                    "Route":       r.get("route", ""),
                    "Timestamp":   (r.get("report_timestamp") or "")[:19],
                    "PDF":         "✅" if r.get("pdf_path") else "❌",
                    "Human":       "✏️" if r.get("human_correction") else "",
                    "Alert":       "🚨" if r.get("alert_sent") else "",
                }
                for r in filtered
            ]
            df = pd.DataFrame(df_rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

        # ── Export ────────────────────────────────────────────────────────
        st.divider()
        exp_col, _ = st.columns([1, 3])
        with exp_col:
            csv_path = export_csv()
            if csv_path and os.path.exists(csv_path):
                with open(csv_path, "rb") as f:
                    st.download_button(
                        "📥 Export All as CSV",
                        data=f.read(),
                        file_name="bridge_inspections.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )
