"""
Prism Report Generator
Reads a run .jsonl and produces matching .db (SQLite) + .html (browsable report).

Run:
  python prism_report.py                          # auto-picks latest in runs/
  python prism_report.py smoke_raw_responses.jsonl  # explicit file
"""
import json, sqlite3, re, sys
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve input file
# ---------------------------------------------------------------------------
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

# Load matching _report.json if present (same dir, same stem + _report)
_report_path = JSONL.parent / (JSONL.stem + "_report.json")
REPORT = json.loads(_report_path.read_text(encoding="utf-8")) if _report_path.exists() else None

# ---------------------------------------------------------------------------
# Load JSONL
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
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        segment      TEXT,
        question_id  TEXT,
        raw_response TEXT,
        parsed_value TEXT
    )
""")
conn.executemany(
    "INSERT INTO responses (segment, question_id, raw_response, parsed_value) VALUES (?,?,?,?)",
    [(r["segment"], r["question_id"], r["raw_response"], r["parsed_value"]) for r in rows]
)
conn.execute("CREATE INDEX IF NOT EXISTS idx_seg_q ON responses(segment, question_id)")
conn.commit()
conn.close()
print(f"DB written -> {DB}  ({len(rows)} rows)")

# ---------------------------------------------------------------------------
# Aggregate helpers
# ---------------------------------------------------------------------------
by_seg_q = defaultdict(list)
for r in rows:
    by_seg_q[(r["segment"], r["question_id"])].append(r)

segments  = list(dict.fromkeys(r["segment"]     for r in rows))
questions = list(dict.fromkeys(r["question_id"] for r in rows))

def mean(vals):
    v = [float(x) for x in vals if x not in (None, "None", "") and re.match(r'^[\d.]+$', str(x))]
    return round(sum(v) / len(v), 2) if v else None

def is_numeric(vals):
    count = sum(1 for v in vals if v not in (None, "None", "") and re.match(r'^[\d.]+$', str(v)))
    return count > len(vals) * 0.5

def base_name(qid):
    s = re.sub(r'^q\d+_', '', qid)
    return re.sub(r'_(anon|named)$', '', s)

anon_qs  = [q for q in questions if q.endswith("_anon")]
named_qs = [q for q in questions if q.endswith("_named")]
sdb_pairs = {}
for aq in anon_qs:
    match = next((nq for nq in named_qs if base_name(nq) == base_name(aq)), None)
    if match:
        sdb_pairs[base_name(aq)] = (aq, match)

# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------
def esc(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def gap_style(gap):
    if gap is None: return ""
    intensity = min(200, int(abs(gap) / 4 * 200))
    return f"background:rgb(255,{255-intensity},{255-intensity})" if gap > 0 else ""

# SDB gap rows
sdb_rows = []
for pair_base, (aq, nq) in sdb_pairs.items():
    sdb_rows.append(f"<tr><th colspan='3' style='background:#c5cae9'>{esc(pair_base)}</th></tr>")
    sdb_rows.append("<tr><th>Segment</th><th>Anon mean</th><th>Named mean</th></tr>")
    for seg in segments:
        a = mean([r["parsed_value"] for r in by_seg_q[(seg, aq)]])
        n = mean([r["parsed_value"] for r in by_seg_q[(seg, nq)]])
        gap = round(a - n, 2) if a is not None and n is not None else None
        bar = "|" * int(abs(gap) * 4) if gap else ""
        style = gap_style(gap)
        gap_str = f"<b>{gap:+.2f}</b> {bar}" if gap is not None else "—"
        sdb_rows.append(f'<tr style="{style}"><td>{esc(seg)}</td><td>{a}</td>'
                        f'<td>{n} &nbsp; gap={gap_str}</td></tr>')

# Per-question summary rows
q_summary_rows = []
for qid in questions:
    q_summary_rows.append(f"<tr><th colspan='{len(segments)+1}' style='background:#c5cae9'>{esc(qid)}</th></tr>")
    q_summary_rows.append("<tr><td><b>metric</b></td>" +
                          "".join(f"<td><b>{esc(s)}</b></td>" for s in segments) + "</tr>")
    all_vals = [r["parsed_value"] for r in by_seg_q.get((segments[0], qid), [])]
    if is_numeric(all_vals):
        cells = []
        for seg in segments:
            m = mean([r["parsed_value"] for r in by_seg_q[(seg, qid)]])
            cells.append(f"<td>{m}</td>" if m is not None else "<td>—</td>")
        q_summary_rows.append("<tr><td>mean</td>" + "".join(cells) + "</tr>")
    else:
        for seg in segments:
            cell = by_seg_q[(seg, qid)]
            sample = esc(cell[0]["raw_response"][:120]) if cell else "—"
            q_summary_rows.append(f'<tr><td>{esc(seg)}</td>'
                                  f'<td colspan="{len(segments)}">{sample}</td></tr>')

# Raw response rows
rows_html = []
for r in rows:
    rows_html.append(
        f'<tr class="r-row" data-seg="{esc(r["segment"])}" data-q="{esc(r["question_id"])}">'
        f'<td>{esc(r["segment"])}</td><td>{esc(r["question_id"])}</td>'
        f'<td>{esc(r["raw_response"])}</td><td>{esc(r["parsed_value"])}</td></tr>'
    )

seg_options = "".join(f'<option value="{esc(s)}">{esc(s)}</option>' for s in segments)
q_options   = "".join(f'<option value="{esc(q)}">{esc(q)}</option>' for q in questions)

# Agent 2 block
if REPORT:
    a2 = REPORT["agent2"]
    score   = esc(str(a2["overall_summary"].get("weighted_reception_score", "—")))
    insight = esc(a2["overall_summary"].get("key_insight", ""))
    target  = esc(a2["target_segment"])
    recs    = "".join(f'<tr><td style="width:2rem;font-weight:bold;text-align:center">{i}</td>'
                      f'<td>{esc(r)}</td></tr>'
                      for i, r in enumerate(a2["recommendations"], 1))
    flags   = "".join(f'<tr><td style="color:#b71c1c">(!) {esc(f)}</td></tr>'
                      for f in a2["risk_flags"])
    agent2_block = f"""
<section id="s-agent2">
<h2>Agent 2 — Strategic Analysis</h2>
<div class="section">
  <table style="margin-bottom:14px">
    <tr><th style="width:130px">Overall Score</th><td><b>{score} / 5</b></td></tr>
    <tr><th>Key Insight</th><td>{insight}</td></tr>
    <tr><th>Target Segment</th><td>{target}</td></tr>
  </table>
  <table style="margin-bottom:14px">
    <thead><tr><th colspan="2">Recommendations</th></tr></thead>
    <tbody>{recs}</tbody>
  </table>
  <table>
    <thead><tr><th>Risk Flags</th></tr></thead>
    <tbody>{flags}</tbody>
  </table>
</div>
</section>"""
    toc_agent2 = '<a href="#s-agent2">Agent 2 Analysis</a>'
else:
    agent2_block = ""
    toc_agent2   = '<a style="opacity:.4" title="No _report.json found">Agent 2 (unavailable)</a>'

toc_segs = "".join(
    f'<a href="#s-raw" class="toc-filter" data-seg="{esc(s)}">{esc(s)}</a>'
    for s in segments
)
toc_qs = "".join(
    f'<a href="#s-raw" class="toc-filter" data-q="{esc(q)}">{esc(q)}</a>'
    for q in questions
)

# ---------------------------------------------------------------------------
# Write HTML
# ---------------------------------------------------------------------------
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Prism Report — {esc(JSONL.name)}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: system-ui, sans-serif; background: #f0f2f5; color: #222;
          display: flex; flex-direction: column; height: 100vh; overflow: hidden; }}

  /* Top bar */
  #topbar {{ background: #1a1a2e; color: #eee; padding: 10px 18px;
             font-size: 0.95rem; font-weight: bold; flex-shrink: 0; }}

  /* Layout */
  #layout {{ display: flex; flex: 1; overflow: hidden; }}

  /* Sidebar TOC */
  #toc {{ width: 210px; min-width: 210px; background: #1e2a3a; color: #aac;
          overflow-y: auto; padding-bottom: 20px; flex-shrink: 0; }}
  #toc .toc-label {{ padding: 10px 14px 4px; font-size: 0.68rem;
                     text-transform: uppercase; color: #556; letter-spacing: .08em; }}
  #toc a {{ display: block; padding: 6px 14px; color: #8ab; text-decoration: none;
             font-size: 0.8rem; border-left: 3px solid transparent;
             white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  #toc a:hover {{ background: #243447; color: #fff; border-left-color: #5b8dee; }}
  #toc a.active {{ background: #1a3050; color: #fff; border-left-color: #5b8dee; }}

  /* Main scrollable area */
  #main {{ flex: 1; overflow-y: auto; overflow-x: auto; }}
  section {{ scroll-margin-top: 4px; }}
  h2 {{ background: #16213e; color: #ccc; padding: 9px 18px; font-size: 0.9rem;
        position: sticky; top: 0; z-index: 10; }}
  .section {{ padding: 14px 18px; }}

  /* Tables */
  table {{ border-collapse: collapse; width: 100%; font-size: 0.82rem; background: #fff; }}
  th, td {{ border: 1px solid #ddd; padding: 5px 9px; text-align: left; vertical-align: top; }}
  th {{ background: #e8eaf6; }}
  tr:hover td {{ background: #f0f4ff; }}

  /* Raw controls */
  .controls {{ padding: 8px 18px; background: #fff; border-bottom: 1px solid #ddd;
               display: flex; gap: 10px; align-items: center; flex-wrap: wrap;
               position: sticky; top: 34px; z-index: 9; }}
  select, input {{ padding: 4px 8px; border: 1px solid #bbb; border-radius: 4px; font-size: 0.85rem; }}
  .count {{ font-size: 0.8rem; color: #666; }}
</style>
</head>
<body>
<div id="topbar">Prism &mdash; Piracy SDB Report &nbsp;|&nbsp; {esc(JSONL.name)} &nbsp;|&nbsp; {len(rows)} responses</div>
<div id="layout">

<nav id="toc">
  <div class="toc-label">Sections</div>
  {toc_agent2}
  <a href="#s-sdb">SDB Gaps</a>
  <a href="#s-summary">Q Summary</a>
  <a href="#s-raw">Raw Responses</a>
  <div class="toc-label">Filter by Segment</div>
  {toc_segs}
  <div class="toc-label">Filter by Question</div>
  {toc_qs}
</nav>

<div id="main">

{agent2_block}

<section id="s-sdb">
<h2>SDB Gaps &mdash; anonymous vs named disclosure</h2>
<div class="section">
<table>
  <tbody>{''.join(sdb_rows)}</tbody>
</table>
</div>
</section>

<section id="s-summary">
<h2>Per-Question Segment Summary</h2>
<div class="section">
<table>
  <thead><tr><th>Question / Metric</th>{''.join(f'<th>{esc(s)}</th>' for s in segments)}</tr></thead>
  <tbody>{''.join(q_summary_rows)}</tbody>
</table>
</div>
</section>

<section id="s-raw">
<h2>Raw Responses</h2>
<div class="controls">
  <label>Segment <select id="seg-filter"><option value="">All</option>{seg_options}</select></label>
  <label>Question <select id="q-filter"><option value="">All</option>{q_options}</select></label>
  <label>Search <input id="search" type="text" placeholder="keyword..." style="width:160px"></label>
  <span class="count" id="count">{len(rows)} shown</span>
</div>
<div class="section" style="padding-top:0">
<table>
  <thead><tr><th>Segment</th><th>Question</th><th>Raw Response</th><th>Parsed</th></tr></thead>
  <tbody>{''.join(rows_html)}</tbody>
</table>
</div>
</section>

</div><!-- #main -->
</div><!-- #layout -->

<script>
const segF  = document.getElementById('seg-filter');
const qF    = document.getElementById('q-filter');
const srch  = document.getElementById('search');
const countEl = document.getElementById('count');
const allRows = Array.from(document.querySelectorAll('.r-row'));

function filter() {{
  const seg = segF.value, q = qF.value, kw = srch.value.toLowerCase();
  let n = 0;
  allRows.forEach(row => {{
    const show = (!seg || row.dataset.seg === seg)
              && (!q   || row.dataset.q   === q)
              && (!kw  || row.textContent.toLowerCase().includes(kw));
    row.style.display = show ? '' : 'none';
    if (show) n++;
  }});
  countEl.textContent = n + ' shown';
}}

segF.addEventListener('change', filter);
qF.addEventListener('change', filter);
srch.addEventListener('input', filter);

// TOC filter links
document.querySelectorAll('.toc-filter').forEach(a => {{
  a.addEventListener('click', e => {{
    e.preventDefault();
    const seg = a.dataset.seg || '', q = a.dataset.q || '';
    if (seg) segF.value = seg;
    if (q)   qF.value   = q;
    filter();
    document.getElementById('s-raw').scrollIntoView({{behavior:'smooth'}});
  }});
}});

// Highlight active TOC link on scroll
const sections = document.querySelectorAll('section[id]');
const tocLinks = document.querySelectorAll('#toc a[href^="#s-"]');
const observer = new IntersectionObserver(entries => {{
  entries.forEach(e => {{
    if (e.isIntersecting) {{
      tocLinks.forEach(l => l.classList.remove('active'));
      const active = document.querySelector('#toc a[href="#' + e.target.id + '"]');
      if (active) active.classList.add('active');
    }}
  }});
}}, {{root: document.getElementById('main'), threshold: 0.2}});
sections.forEach(s => observer.observe(s));
</script>
</body>
</html>"""

HTML.write_text(html, encoding="utf-8")
print(f"HTML written -> {HTML}")
