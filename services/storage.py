"""
services/storage.py
Local JSON-based persistence for inspection logs.
"""
import json
import os
import csv
from typing import Optional

DATA_DIR = "data"
INSPECTIONS_FILE = os.path.join(DATA_DIR, "inspections.json")


def _ensure_data_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(INSPECTIONS_FILE):
        with open(INSPECTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)


def _serialize(state: dict) -> dict:
    """Remove non-serializable fields (image bytes) before saving."""
    skip = {"image_bytes"}
    return {k: v for k, v in state.items() if k not in skip}


def save_inspection(state: dict) -> None:
    """Insert or update an inspection record by inspection_id."""
    _ensure_data_dir()
    with open(INSPECTIONS_FILE, "r", encoding="utf-8") as f:
        records: list = json.load(f)

    record = _serialize(state)
    idx = next(
        (i for i, r in enumerate(records)
         if r.get("inspection_id") == record.get("inspection_id")),
        None,
    )
    if idx is not None:
        records[idx] = record
    else:
        records.append(record)

    with open(INSPECTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)


def load_all_inspections() -> list:
    _ensure_data_dir()
    with open(INSPECTIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_inspection(inspection_id: str) -> Optional[dict]:
    return next(
        (r for r in load_all_inspections()
         if r.get("inspection_id") == inspection_id),
        None,
    )


def export_csv() -> str:
    """Export all records to CSV; returns path."""
    records = load_all_inspections()
    if not records:
        return ""

    csv_path = os.path.join(DATA_DIR, "inspections_export.csv")
    fields = [
        "inspection_id", "prefecture_id", "image_filename",
        "damage_type", "severity_rank", "confidence", "notes",
        "route", "report_timestamp", "pdf_path",
        "alert_sent", "human_correction",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)

    return csv_path
