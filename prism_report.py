"""
Prism Report Generator
Reads smoke_raw_responses.jsonl and produces:
  - prism_responses.db   (SQLite)
  - prism_report.html    (browsable report)

Run: python prism_report.py
"""
import json
import sqlite3
import re
from collections import defaultdict
from pathlib import Path

import sys

if len(sys.argv) > 1:
    JSONL = Path(sys.argv[1])
else:
    runs = sorted(Path("runs").glob("*.jsonl")) if Path("runs").exists() else []
    if not runs:
        print("No runs/ folder found. Pass a .jsonl path as argument.")
        sys.exit(1)
    JSONL = runs[-1]
    print(f"Using latest run: {JSONL}")

DB   = JSONL.parent / (JSONL.stem + ".db")
HTML = JSONL.parent / (JSONL.stem + ".html")

# Load matching _report.json if present
_report_path = JSONL.parent / (JSONL.stem + "_report.json")
REPORT = json.loads(_report_path.read_text(encoding="utf-8")) if _report_path.exists() else None

# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------
rows = []
with open(JSONL, encoding="utf-8") as f:
    for line in f:
        rows.append(json.loads(line))

# ---------------------------------------------------------------------------
# SQLite
# ---------------------------------------------------------------------------
conn = sqlite3.connect(DB)
conn.execute("DROP TABLE IF EXISTS responses")
conn.execute("""
    CREATE TABLE responses (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        segment       TEXT,
        question_id   TEXT,
        raw_response  TEXT,
        parsed_value  TEXT
    )
""")
conn.executemany(
    "INSERT INTO responses (segment, question_id, raw_response, parsed_value) VALUES (?,?,?,?)",
    [(r["segment"], r["question_id"], r["raw_response"], r["parsed_value"]) for r in rows]
)
conn.execute("CREATE INDEX IF NOT EXISTS idx_seg_q ON responses(segment, question_id)")
conn.commit()
conn.close()
print(f"DB written → {DB}  ({len(rows)} rows)")

# ---------------------------------------------------------------------------
# Aggregate for HTML
# ---------------------------------------------------------------------------
# Group by (segment, question_id)
by_seg_q = defaultdict(list)
for r in rows:
    by_seg_q[(r["segment"], r["question_id"])].append(r)

segments  = list(dict.fromkeys(r["segment"] for r in rows))
questions = list(dict.fromkeys(r["question_id"] for r in rows))

def mean(vals):
    v = [float(x) for x in vals if x not in (None, "None", "")]
    return round(sum(v) / len(v), 2) if v else None

def pct_yes(vals):
    v = [x for x in vals if x in ("1", "0")]
    return round(100 * sum(int(x) for x in v) / len(v), 1) if v else None

def is_numeric(vals):
    count = sum(1 for v in vals if v not in (None, "None", "") and re.match(r'^[\d.]+$', str(v)))
    return count > len(vals) * 0.5

# Detect SDB pairs
def base_name(qid):
    s = re.sub(r'^q\d+_', '', qid)
    s = re.sub(r'_(anon|named)$', '', s)
    return s

anon_qs  = [q for q in questions if q.endswith("_anon")]
named_qs = [q for q in questions if q.endswith("_named")]
sdb_pairs = {}
for aq in anon_qs:
    match = next((nq for nq in named_qs if base_name(nq) == base_name(aq)), None)
    if match:
        sdb_pairs[base_name(aq)] = (aq, match)

# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------
def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def color_gap(gap):
    if gap is None: return ""
    r = min(255, int(abs(gap) / 4 * 200))
    return f"background:#ff{255-r:02x}{255-r:02x}" if gap > 0 else f"background:#ffffff"

rows_html = []
for r in rows:
    rows_html.append(f"""<tr class="r-row" data-seg="{esc(r['segment'])}" data-q="{esc(r['question_id'])}">
      <td>{esc(r['segment'])}</td>
      <td>{esc(r['question_id'])}</td>
      <td>{esc(r['raw_response'])}</td>
      <td>{esc(r['parsed_value'])}</td>
    </tr>""")

# SDB gap table rows
sdb_rows = []
for pair_base, (aq, nq) in sdb_pairs.items():
    sdb_rows.append(f"<tr><th colspan='2'>{esc(pair_base)}</th></tr>")
    for seg in segments:
        anon_vals = [r["parsed_value"] for r in by_seg_q[(seg, aq)]]
        named_vals = [r["parsed_value"] for r in by_seg_q[(seg, nq)]]
        a_mean = mean(anon_vals)
        n_mean = mean(named_vals)
        gap = round(a_mean - n_mean, 2) if a_mean and n_mean else None
        bar = "|" * int(abs(gap) * 4) if gap else ""
        style = color_gap(gap)
        sdb_rows.append(f'<tr style="{style}"><td>{esc(seg)}</td>'
                        f'<td>anon={a_mean} | named={n_mean} | <b>gap={gap:+.2f}</b> {bar}</td></tr>')

# Per-question summary rows
q_summary_rows = []
for qid in questions:
    q_summary_rows.append(f"<tr><th colspan='{len(segments)+1}'>{esc(qid)}</th></tr>")
    header = "<tr><td><b>metric</b></td>" + "".join(f"<td><b>{esc(s)}</b></td>" for s in segments) + "</tr>"
    q_summary_rows.append(header)

    # mean (if numeric)
    all_vals = [r["parsed_value"] for r in by_seg_q.get((segments[0], qid), [])]
    if is_numeric(all_vals):
        means = []
        for seg in segments:
            vals = [r["parsed_value"] for r in by_seg_q[(seg, qid)]]
            m = mean(vals)
            means.append(f"<td>{m}/5</td>" if m else "<td>—</td>")
        q_summary_rows.append("<tr><td>mean</td>" + "".join(means) + "</tr>")
    else:
        # open-ended: show sample
        for seg in segments:
            cell_rows = by_seg_q[(seg, qid)]
            sample = cell_rows[0]["raw_response"][:120] if cell_rows else "—"
            q_summary_rows.append(f'<tr><td>{esc(seg)}</td><td colspan="{len(segments)}">{esc(sample)}</td></tr>')

seg_options = "".join(f'<option value="{esc(s)}">{esc(s)}</option>' for s in segments)
q_options   = "".join(f'<option value="{esc(q)}">{esc(q)}</option>' for q in questions)

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Prism — Piracy SDB Report</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 0; background: #f5f5f5; color: #222; }}
  h1 {{ background: #1a1a2e; color: #eee; margin: 0; padding: 16px 24px; font-size: 1.2rem; }}
  h2 {{ background: #16213e; color: #ccc; margin: 0; padding: 10px 24px; font-size: 1rem; }}
  .section {{ padding: 20px 24px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.85rem; background: #fff; }}
  th, td {{ border: 1px solid #ddd; padding: 6px 10px; text-align: left; vertical-align: top; }}
  th {{ background: #e8eaf6; }}
  tr:hover td {{ background: #f0f4ff; }}
  .controls {{ padding: 12px 24px; background: #fff; border-bottom: 1px solid #ddd; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }}
  select, input {{ padding: 6px 10px; border: 1px solid #bbb; border-radius: 4px; font-size: 0.9rem; }}
  .count {{ font-size: 0.85rem; color: #666; }}
  .tag {{ display: inline-block; background: #e3f2fd; border-radius: 3px; padding: 1px 6px; font-size: 0.75rem; margin-left: 4px; }}
</style>
</head>
<body>
<h1>Prism — Piracy SDB Study · Raw Response Report</h1>

{"" if not REPORT else f"""
<h2>0. Agent 2 — Strategic Analysis</h2>
<div class="section">
  <table>
    <tr><th>Overall Score</th><td>{esc(str(REPORT['agent2']['overall_summary'].get('weighted_reception_score', '—')))}/5</td></tr>
    <tr><th>Key Insight</th><td>{esc(REPORT['agent2']['overall_summary'].get('key_insight', ''))}</td></tr>
    <tr><th>Target Segment</th><td>{esc(REPORT['agent2']['target_segment'])}</td></tr>
  </table>
  <br>
  <table>
    <thead><tr><th>#</th><th>Recommendation</th></tr></thead>
    <tbody>{''.join(f"<tr><td>{i}</td><td>{esc(r)}</td></tr>" for i, r in enumerate(REPORT['agent2']['recommendations'], 1))}</tbody>
  </table>
  <br>
  <table>
    <thead><tr><th>Risk Flags</th></tr></thead>
    <tbody>{''.join(f"<tr><td>(!) {esc(f)}</td></tr>" for f in REPORT['agent2']['risk_flags'])}</tbody>
  </table>
</div>
"""}

<h2>1. Social Desirability Bias Gaps</h2>
<div class="section">
<table>
  <thead><tr><th>Segment</th><th>anon vs named (gap = anon − named)</th></tr></thead>
  <tbody>{''.join(sdb_rows)}</tbody>
</table>
</div>

<h2>2. Per-Question Segment Summary</h2>
<div class="section">
<table>
  <thead><tr><th>Question / Metric</th>{''.join(f'<th>{esc(s)}</th>' for s in segments)}</tr></thead>
  <tbody>{''.join(q_summary_rows)}</tbody>
</table>
</div>

<h2>3. Raw Responses ({len(rows)} total)</h2>
<div class="controls">
  <label>Segment: <select id="seg-filter"><option value="">All</option>{seg_options}</select></label>
  <label>Question: <select id="q-filter"><option value="">All</option>{q_options}</select></label>
  <label>Search raw: <input id="search" type="text" placeholder="keyword..." style="width:200px"></label>
  <span class="count" id="count">{len(rows)} rows shown</span>
</div>
<div class="section" style="padding-top:0">
<table id="raw-table">
  <thead><tr><th>Segment</th><th>Question</th><th>Raw Response</th><th>Parsed</th></tr></thead>
  <tbody>{''.join(rows_html)}</tbody>
</table>
</div>

<script>
const segF  = document.getElementById('seg-filter');
const qF    = document.getElementById('q-filter');
const srch  = document.getElementById('search');
const count = document.getElementById('count');
const allRows = Array.from(document.querySelectorAll('.r-row'));

function filter() {{
  const seg = segF.value;
  const q   = qF.value;
  const kw  = srch.value.toLowerCase();
  let n = 0;
  allRows.forEach(row => {{
    const show = (!seg || row.dataset.seg === seg)
              && (!q   || row.dataset.q   === q)
              && (!kw  || row.textContent.toLowerCase().includes(kw));
    row.style.display = show ? '' : 'none';
    if (show) n++;
  }});
  count.textContent = n + ' rows shown';
}}

segF.addEventListener('change', filter);
qF.addEventListener('change', filter);
srch.addEventListener('input', filter);
</script>
</body>
</html>"""

HTML.write_text(html, encoding="utf-8")
print(f"HTML written → {HTML}")
print("Open prism_report.html in browser.")
