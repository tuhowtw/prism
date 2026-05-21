"""
prism_session.py — manifest read/write, run listing, zip export/import.
"""
from __future__ import annotations

import io
import json
import os
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

# Import dataclasses from engine for serialization helpers
from prism_engine import Segment, SurveyQuestion, ClarifyQuestion

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RUNS_DIR = Path("runs")

TZ_TAIPEI = timezone(timedelta(hours=8))

# ---------------------------------------------------------------------------
# Run ID + directory helpers
# ---------------------------------------------------------------------------

def make_run_id(n_per_cell: int) -> str:
    """Returns e.g. '20260502_173045_n8'."""
    now = datetime.now(tz=TZ_TAIPEI)
    return now.strftime("%Y%m%d_%H%M%S") + f"_n{n_per_cell}"


def run_dir(run_id: str) -> Path:
    """Returns Path('runs/{run_id}'), creates if needed."""
    d = RUNS_DIR / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Manifest I/O
# ---------------------------------------------------------------------------

def save_manifest(manifest: dict) -> None:
    """Atomic write: write to .tmp then rename."""
    run_id = manifest["id"]
    d = run_dir(run_id)
    target = d / "manifest.json"
    tmp = d / "manifest.json.tmp"
    tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(target)


def load_manifest(run_id: str) -> dict | None:
    """Returns None if not found."""
    p = RUNS_DIR / run_id / "manifest.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def list_runs() -> list[dict]:
    """Returns list of manifests sorted by created_at desc."""
    if not RUNS_DIR.exists():
        return []
    manifests = []
    for p in RUNS_DIR.glob("*/manifest.json"):
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
            manifests.append(m)
        except Exception:
            continue
    manifests.sort(key=lambda m: m.get("created_at", ""), reverse=True)
    return manifests


# ---------------------------------------------------------------------------
# Zip export / import
# ---------------------------------------------------------------------------

def export_zip(run_id: str) -> bytes:
    """Zip the entire runs/{run_id}/ folder. Returns bytes."""
    d = RUNS_DIR / run_id
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in d.rglob("*"):
            if f.is_file():
                arcname = f.relative_to(RUNS_DIR)
                zf.write(f, arcname)
    return buf.getvalue()


def import_zip(zip_bytes: bytes) -> str:
    """Extract zip into runs/. Returns run_id."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO(zip_bytes)
    with zipfile.ZipFile(buf, "r") as zf:
        # Peek at first path component to derive run_id
        names = zf.namelist()
        if not names:
            raise ValueError("Empty zip archive")
        # First path component is the run_id directory
        run_id = Path(names[0]).parts[0]
        zf.extractall(RUNS_DIR)
    return run_id


# ---------------------------------------------------------------------------
# Dataclass ↔ dict helpers
# ---------------------------------------------------------------------------

def segment_to_dict(seg: Segment) -> dict:
    return {
        "name": seg.name,
        "description": seg.description,
        "weight": seg.weight,
        "rationale": seg.rationale,
    }


def question_to_dict(q: SurveyQuestion) -> dict:
    return {
        "id": q.id,
        "text": q.text,
        "type": q.type,
        "scale_label": q.scale_label,
        "options": q.options,
        "condition": q.condition,
    }


def clarify_to_dict(cq: ClarifyQuestion) -> dict:
    return {
        "id": cq.id,
        "axis": cq.axis,
        "text": cq.text,
        "why": cq.why,
        "answer_type": cq.answer_type,
        "options": cq.options,
        "allow_freeform": cq.allow_freeform,
        "skippable": cq.skippable,
        "priority": cq.priority,
    }


def segment_from_dict(d: dict) -> Segment:
    return Segment(
        name=d["name"],
        description=d["description"],
        weight=float(d["weight"]),
        rationale=d["rationale"],
    )


def question_from_dict(d: dict) -> SurveyQuestion:
    return SurveyQuestion(
        id=d["id"],
        text=d["text"],
        type=d["type"],
        scale_label=d.get("scale_label", ""),
        options=d.get("options", []),
        condition=d.get("condition", "neutral"),
    )


def clarify_from_dict(d: dict) -> ClarifyQuestion:
    return ClarifyQuestion(
        id=d["id"],
        axis=d["axis"],
        text=d["text"],
        why=d["why"],
        answer_type=d["answer_type"],
        options=d.get("options", []),
        allow_freeform=d.get("allow_freeform", True),
        skippable=d.get("skippable", True),
        priority=d.get("priority", "nice"),
    )
