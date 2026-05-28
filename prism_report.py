"""
Prism Report Generator
Reads a run .jsonl and produces matching .db (SQLite) + .html (browsable report).

Run:
  python prism_report.py                            # auto-picks latest in runs/
  python prism_report.py smoke_raw_responses.jsonl  # explicit file
"""
import ast, json, re, sqlite3, sys
from collections import Counter, defaultdict
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
conn.execute("DROP TABLE IF EXISTS segments")
conn.execute("DROP TABLE IF EXISTS questions")
conn.execute("""
    CREATE TABLE responses (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        segment      TEXT,
        question_id  TEXT,
        raw_response TEXT,
        parsed_value TEXT,
        pmf          TEXT
    )
""")
conn.execute("""
    CREATE TABLE segments (
        name        TEXT PRIMARY KEY,
        weight      REAL,
        description TEXT,
        rationale   TEXT
    )
""")
conn.execute("""
    CREATE TABLE questions (
        id          TEXT PRIMARY KEY,
        text        TEXT,
        type        TEXT,
        condition   TEXT,
        scale_label TEXT,
        options     TEXT
    )
""")
conn.executemany(
    "INSERT INTO responses (segment, question_id, raw_response, parsed_value, pmf) VALUES (?,?,?,?,?)",
    [(r["segment"], r["question_id"], r["raw_response"], r["parsed_value"],
      json.dumps(r["pmf"]) if r.get("pmf") is not None else None) for r in rows]
)
if REPORT and "segments" in REPORT:
    conn.executemany(
        "INSERT OR IGNORE INTO segments (name, weight, description, rationale) VALUES (?,?,?,?)",
        [(s["name"], s.get("weight",0), s.get("description",""), s.get("rationale",""))
         for s in REPORT["segments"]]
    )
if REPORT and "questions" in REPORT:
    conn.executemany(
        "INSERT OR IGNORE INTO questions (id, text, type, condition, scale_label, options) VALUES (?,?,?,?,?,?)",
        [(q["id"], q.get("text",""), q.get("type",""), q.get("condition","neutral"),
          q.get("scale_label",""), json.dumps(q.get("options",[])))
         for q in REPORT["questions"]]
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
    v = [float(x) for x in vals
         if x not in (None, "None", "") and re.match(r'^[\d.]+$', str(x))]
    return round(sum(v) / len(v), 2) if v else None

def stdev(vals):
    v = [float(x) for x in vals
         if x not in (None, "None", "") and re.match(r'^[\d.]+$', str(x))]
    if len(v) < 2:
        return None
    m = sum(v) / len(v)
    return round((sum((x - m) ** 2 for x in v) / (len(v) - 1)) ** 0.5, 2)

def is_numeric(vals):
    count = sum(1 for v in vals
                if v not in (None, "None", "") and re.match(r'^[\d.]+$', str(v)))
    return count > len(vals) * 0.5

def parse_ms(pv):
    try:
        v = ast.literal_eval(str(pv))
        return v if isinstance(v, list) else []
    except Exception:
        return []

def base_name(qid):
    s = re.sub(r'^q\d+_', '', qid)
    return re.sub(r'_(anon|named)$', '', s)

# SDB pairs
anon_qs  = [q for q in questions if q.endswith("_anon")]
named_qs = [q for q in questions if q.endswith("_named")]
sdb_pairs = {}
for aq in anon_qs:
    nq = next((nq for nq in named_qs if base_name(nq) == base_name(aq)), None)
    if nq:
        sdb_pairs[base_name(aq)] = (aq, nq)

named_paired = {nq for _, nq in sdb_pairs.values()}
anon_set     = {aq for aq, _ in sdb_pairs.values()}

# Sanity-check pairs
v1_qs  = [q for q in questions if q.endswith("_v1")]
v2_qs  = [q for q in questions if q.endswith("_v2")]
pos_qs = [q for q in questions if q.endswith("_pos")]
neg_qs = [q for q in questions if q.endswith("_neg")]

consistency_pairs = {}  # prefix -> (v1_id, v2_id)
for v1id in v1_qs:
    base = v1id[:-3]
    v2id = next((i for i in v2_qs if i[:-3] == base), None)
    if v2id:
        consistency_pairs[base] = (v1id, v2id)

reverse_pairs = {}  # prefix -> (pos_id, neg_id)
for pid in pos_qs:
    base = pid[:-4]
    nid = next((i for i in neg_qs if i[:-4] == base), None)
    if nid:
        reverse_pairs[base] = (pid, nid)

sanity_paired = (
    {v2id for _, v2id in consistency_pairs.values()} |
    {nid for _, nid in reverse_pairs.values()}
)

# Question metadata from report JSON (has type, text, condition, options)
q_meta = {}
if REPORT and "questions" in REPORT:
    for q in REPORT["questions"]:
        q_meta[q["id"]] = q
else:
    for qid in questions:
        vals = [r["parsed_value"] for r in by_seg_q.get((segments[0], qid), [])]
        if vals and is_numeric(vals):
            mx = max((float(v) for v in vals if re.match(r'^[\d.]+$', str(v))), default=5)
            q_meta[qid] = {"type": "wtp" if mx > 5 else "likert5", "text": qid, "condition": "neutral", "options": []}
        elif vals and str(vals[0]).startswith("["):
            q_meta[qid] = {"type": "multi_select", "text": qid, "condition": "neutral", "options": []}
        else:
            q_meta[qid] = {"type": "open", "text": qid, "condition": "neutral", "options": []}

# ---------------------------------------------------------------------------
# SVG chart helpers
# ---------------------------------------------------------------------------
SEG_COLORS = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f", "#b07aa1"]

def _p(n): return f"{round(float(n), 1)}"
def esc(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")


def svg_sdb_hbar(labels, values, vmax=5.0, width=520):
    """Horizontal bar chart for SDB gaps, sorted descending."""
    LM, RM, row_h = 190, 70, 32
    BW = width - LM - RM
    h = len(labels) * row_h + 24
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{h}" '
             f'style="font-family:system-ui,sans-serif;font-size:11px;display:block">']
    # axis label
    parts.append(f'<text x="{LM + BW/2}" y="12" text-anchor="middle" fill="#888" font-size="9">'
                 f'Gap (anon − named, 1–5 scale)</text>')
    for i, (label, val) in enumerate(zip(labels, values)):
        y = i * row_h + 18
        cy = y + row_h / 2
        bar_w = max(3, BW * val / (vmax if vmax > 0 else 1))
        intensity = min(200, int(val / vmax * 200)) if vmax else 0
        fill = f"rgb({220},{120 - intensity//3},{60 - intensity//4})"
        parts.append(f'<rect x="{LM}" y="{y+3}" width="{BW}" height="{row_h-6}" fill="#f0f2f5" rx="3"/>')
        parts.append(f'<rect x="{LM}" y="{y+3}" width="{_p(bar_w)}" height="{row_h-6}" fill="{fill}" rx="3" opacity="0.85"/>')
        parts.append(f'<text x="{LM-8}" y="{_p(cy+4)}" text-anchor="end" fill="#334">{esc(label)}</text>')
        parts.append(f'<text x="{_p(LM + bar_w + 7)}" y="{_p(cy+4)}" fill="#555" font-weight="bold">+{val:.2f}</text>')
    parts.append('</svg>')
    return "".join(parts)


def svg_vbar(seg_labels, values, vmin=0, vmax=5, width=480, height=160,
             colors=None, series_label="", y_suffix=""):
    """Vertical bar chart, one bar per segment, segment-colored."""
    LM, RM, TM, BM = 38, 8, 8, 48
    cw, ch = width - LM - RM, height - TM - BM
    n = len(seg_labels)
    group_w = cw / n
    bar_w = group_w * 0.55
    pad = (group_w - bar_w) / 2
    if colors is None:
        colors = SEG_COLORS

    def yp(v):
        v = max(vmin, min(vmax, v or 0))
        return TM + ch - ch * (v - vmin) / (vmax - vmin)

    steps = 5 if (vmax - vmin) <= 5 else 4
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'style="font-family:system-ui,sans-serif;font-size:10px;display:block">']
    # grid
    for t in range(steps + 1):
        v = vmin + t * (vmax - vmin) / steps
        y = yp(v)
        parts.append(f'<line x1="{LM}" y1="{_p(y)}" x2="{width-RM}" y2="{_p(y)}" stroke="#e8e8e8"/>')
        parts.append(f'<text x="{LM-4}" y="{_p(y+3)}" text-anchor="end" fill="#aaa">{round(v,1)}{y_suffix}</text>')
    # bars
    for j, (seg, val, color) in enumerate(zip(seg_labels, values, colors)):
        bx = LM + j * group_w + pad
        v = val if val is not None else 0
        y0, y1 = yp(0 if vmin <= 0 else vmin), yp(v)
        bh = abs(y0 - y1)
        parts.append(f'<rect x="{_p(bx)}" y="{_p(min(y0,y1))}" width="{_p(bar_w)}" '
                     f'height="{_p(max(1,bh))}" fill="{color}" rx="3" opacity="0.85"/>')
        if bh > 14:
            parts.append(f'<text x="{_p(bx+bar_w/2)}" y="{_p(min(y0,y1)-3)}" '
                         f'text-anchor="middle" fill="#333" font-size="9" font-weight="bold">'
                         f'{round(v,1)}{y_suffix}</text>')
        # x-label (wrap at 12 chars)
        label = seg if len(seg) <= 14 else seg[:12] + ".."
        parts.append(f'<text x="{_p(bx+bar_w/2)}" y="{height-BM+14}" '
                     f'text-anchor="middle" fill="#555" font-size="9">{esc(label)}</text>')
    parts.append('</svg>')
    return "".join(parts)


def svg_grouped_vbar(seg_labels, anon_vals, named_vals, vmin=1, vmax=5, width=480, height=160):
    """Two-series grouped bar: anon (orange) vs named (blue) per segment."""
    LM, RM, TM, BM = 38, 8, 8, 48
    cw, ch = width - LM - RM, height - TM - BM
    n = len(seg_labels)
    group_w = cw / n
    bar_w = group_w * 0.32
    gap = group_w * 0.06
    ANON_C, NAMED_C = "#f28e2b", "#4e79a7"

    def yp(v):
        v = max(vmin, min(vmax, v or vmin))
        return TM + ch - ch * (v - vmin) / (vmax - vmin)

    steps = int(vmax - vmin)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'style="font-family:system-ui,sans-serif;font-size:10px;display:block">']
    for t in range(steps + 1):
        v = vmin + t
        y = yp(v)
        parts.append(f'<line x1="{LM}" y1="{_p(y)}" x2="{width-RM}" y2="{_p(y)}" stroke="#e8e8e8"/>')
        parts.append(f'<text x="{LM-4}" y="{_p(y+3)}" text-anchor="end" fill="#aaa">{v}</text>')

    for j, seg in enumerate(seg_labels):
        gx = LM + j * group_w + (group_w - 2*bar_w - gap) / 2
        for s, (val, color, label) in enumerate(zip([anon_vals[j], named_vals[j]],
                                                     [ANON_C, NAMED_C],
                                                     ["Anon", "Named"])):
            bx = gx + s * (bar_w + gap)
            v = val if val is not None else vmin
            y0, y1 = yp(vmin), yp(v)
            bh = abs(y0 - y1)
            parts.append(f'<rect x="{_p(bx)}" y="{_p(min(y0,y1))}" width="{_p(bar_w)}" '
                         f'height="{_p(max(1,bh))}" fill="{color}" rx="2" opacity="0.85"/>')
            if bh > 12:
                parts.append(f'<text x="{_p(bx+bar_w/2)}" y="{_p(min(y0,y1)-2)}" '
                             f'text-anchor="middle" fill="#333" font-size="8">{round(v,1)}</text>')
        seg_short = seg if len(seg) <= 14 else seg[:12] + ".."
        cx = gx + bar_w + gap / 2
        parts.append(f'<text x="{_p(cx)}" y="{height-BM+14}" text-anchor="middle" fill="#555" font-size="9">'
                     f'{esc(seg_short)}</text>')

    # legend
    lx = LM
    for color, label in [(ANON_C, "Anonymous"), (NAMED_C, "Named")]:
        parts.append(f'<rect x="{_p(lx)}" y="{height-BM+26}" width="9" height="9" fill="{color}" rx="2"/>')
        parts.append(f'<text x="{_p(lx+12)}" y="{height-BM+35}" fill="#555">{label}</text>')
        lx += 80
    parts.append('</svg>')
    return "".join(parts)


def svg_histogram(counts_dict, width=108, height=60):
    """Tiny Likert 1-5 histogram."""
    bins = [1, 2, 3, 4, 5]
    counts = [counts_dict.get(b, 0) for b in bins]
    max_c = max(counts) if max(counts) > 0 else 1
    LM, RM, TM, BM = 3, 3, 3, 14
    cw, ch = width-LM-RM, height-TM-BM
    bar_w = cw / 5 * 0.72
    HIST_C = ["#e15759","#f28e2b","#edc948","#76b7b2","#59a14f"]
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'style="font-family:system-ui,sans-serif;font-size:8px;display:inline-block">']
    for i, (b, c, col) in enumerate(zip(bins, counts, HIST_C)):
        bx = LM + i * (cw/5) + (cw/5 - bar_w)/2
        bh = ch * c / max_c
        by = TM + ch - bh
        parts.append(f'<rect x="{_p(bx)}" y="{_p(by)}" width="{_p(bar_w)}" '
                     f'height="{_p(max(1,bh))}" fill="{col}" rx="1" opacity="0.8"/>')
        parts.append(f'<text x="{_p(bx+bar_w/2)}" y="{height-3}" text-anchor="middle" fill="#999">{b}</text>')
        if c > 0 and bh > 9:
            parts.append(f'<text x="{_p(bx+bar_w/2)}" y="{_p(by-1)}" text-anchor="middle" fill="#666">{c}</text>')
    parts.append('</svg>')
    return "".join(parts)


def svg_heatmap(row_labels, col_labels, matrix, cell_w=100, cell_h=26, label_w=170):
    """Heatmap: rows=options, cols=segments, values in [0,100]."""
    header_h = 32
    width  = label_w + cell_w * len(col_labels) + 6
    height = header_h + cell_h * len(row_labels) + 6
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'style="font-family:system-ui,sans-serif;font-size:10px;display:block">']
    # column headers
    for j, col in enumerate(col_labels):
        cx = label_w + j * cell_w + cell_w / 2
        short = col if len(col) <= 14 else col[:12] + ".."
        parts.append(f'<text x="{_p(cx)}" y="14" text-anchor="middle" fill="#334" '
                     f'font-size="9" font-weight="bold">{esc(short)}</text>')
    for i, row_lbl in enumerate(row_labels):
        y = header_h + i * cell_h
        short_row = row_lbl if len(row_lbl) <= 24 else row_lbl[:22] + ".."
        parts.append(f'<text x="{label_w-6}" y="{_p(y+cell_h/2+4)}" text-anchor="end" '
                     f'fill="#334" font-size="9">{esc(short_row)}</text>')
        for j, col in enumerate(col_labels):
            val = matrix[i][j] if matrix[i][j] is not None else 0
            cx = label_w + j * cell_w
            intens = int(val / 100 * 190)
            r_c = 255 - intens // 3
            g_c = 255 - intens // 2
            b_c = 255
            txt_c = "#fff" if intens > 130 else "#334"
            parts.append(f'<rect x="{_p(cx)}" y="{y}" width="{cell_w-2}" '
                         f'height="{cell_h-2}" fill="rgb({r_c},{g_c},{b_c})" rx="2"/>')
            parts.append(f'<text x="{_p(cx+cell_w/2)}" y="{_p(y+cell_h/2+4)}" '
                         f'text-anchor="middle" fill="{txt_c}" font-weight="bold" font-size="9">'
                         f'{round(val)}%</text>')
    parts.append('</svg>')
    return "".join(parts)


def _svg_pmf_dist(seg_labels, pmf_rows, width=460, height=60):
    """Small stacked pmf bar for each segment showing SSR Likert distribution."""
    COLORS_5 = ["#d73027", "#fc8d59", "#ffffbf", "#91cf60", "#1a9850"]
    LM, RM, TM = 4, 4, 18
    bw = (width - LM - RM) / max(len(seg_labels), 1)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'style="font-family:system-ui,sans-serif;font-size:8px;display:block;margin-top:4px">'
        f'<text x="{LM}" y="10" fill="#aaa" font-size="8">SSR distribution</text>'
    ]
    bar_h = height - TM - 4
    for j, (seg, pmf) in enumerate(zip(seg_labels, pmf_rows)):
        x0 = LM + j * bw
        cx = x0 + bw * 0.1
        bw2 = bw * 0.8
        y_off = TM
        for i, p in enumerate(pmf):
            seg_h = bar_h * p
            parts.append(
                f'<rect x="{_p(cx)}" y="{_p(y_off + bar_h - sum(bar_h * pmf[k] for k in range(i+1)))}" '
                f'width="{_p(bw2)}" height="{_p(max(1, seg_h))}" fill="{COLORS_5[i]}" opacity="0.85"/>'
            )
        short = seg[:10]
        parts.append(f'<text x="{_p(cx + bw2/2)}" y="{_p(height - 2)}" text-anchor="middle" fill="#666">{esc(short)}</text>')
    parts.append('</svg>')
    return "".join(parts)


# ---------------------------------------------------------------------------
# Build chart grid for per-question section
# ---------------------------------------------------------------------------
def hist_row_html(qid):
    """Row of mini histograms (one per segment) for a Likert question."""
    parts = ['<div style="display:flex;gap:6px;margin-top:6px;flex-wrap:wrap">']
    for seg, color in zip(segments, SEG_COLORS):
        vals = [r["parsed_value"] for r in by_seg_q[(seg, qid)]]
        cd = {i: sum(1 for v in vals if v == str(i)) for i in range(1, 6)}
        short = seg if len(seg) <= 14 else seg[:12] + ".."
        parts.append(f'<div style="text-align:center">'
                     f'<div style="font-size:8px;color:{color};font-weight:bold;margin-bottom:2px">'
                     f'{esc(short)}</div>'
                     f'{svg_histogram(cd)}</div>')
    parts.append('</div>')
    return "".join(parts)


chart_cards = []

for qid in questions:
    if qid in named_paired:
        continue  # handled in the anon card

    meta  = q_meta.get(qid, {})
    qtype = meta.get("type", "likert5")
    qtext = meta.get("text", qid)

    # ── Anon/named paired ──
    if qid in anon_set:
        pair_base = next(pb for pb, (aq, nq) in sdb_pairs.items() if aq == qid)
        nq = sdb_pairs[pair_base][1]
        a_means  = [mean([r["parsed_value"] for r in by_seg_q[(seg, qid)]]) for seg in segments]
        n_means  = [mean([r["parsed_value"] for r in by_seg_q[(seg, nq)]])  for seg in segments]
        chart_html = svg_grouped_vbar(segments, a_means, n_means) + hist_row_html(qid)
        title = f"[SDB pair] {qtext[:80]}"

    # ── Likert neutral ──
    elif qtype == "likert5":
        means = [mean([r["parsed_value"] for r in by_seg_q[(seg, qid)]]) for seg in segments]
        sds   = [stdev([r["parsed_value"] for r in by_seg_q[(seg, qid)]]) for seg in segments]
        sd_labels = " &nbsp;|&nbsp; ".join(
            f'<span style="color:{c}">{esc(s)} σ={_p(sd) if sd else "—"}</span>'
            for s, sd, c in zip(segments, sds, SEG_COLORS)
        )
        sd_row = f'<div style="font-size:9px;color:#888;margin-top:3px">{sd_labels}</div>'
        # If SSR pmf data is available, show aggregate distribution bar
        pmf_rows = []
        for seg in segments:
            pmf_vals = []
            for r in by_seg_q[(seg, qid)]:
                raw_pmf = r.get("pmf")
                if raw_pmf is not None:
                    try:
                        p = json.loads(raw_pmf) if isinstance(raw_pmf, str) else raw_pmf
                        if isinstance(p, list) and len(p) == 5:
                            pmf_vals.append(p)
                    except Exception:
                        pass
            if pmf_vals:
                avg_pmf = [round(sum(p[i] for p in pmf_vals) / len(pmf_vals), 3) for i in range(5)]
                pmf_rows.append(avg_pmf)
        pmf_html = ""
        if pmf_rows:
            pmf_html = _svg_pmf_dist(segments, pmf_rows)
        chart_html = svg_vbar(segments, means, vmin=1, vmax=5) + hist_row_html(qid) + sd_row + pmf_html
        title = qtext[:90]

    # ── WTP ──
    elif qtype == "wtp":
        means = [mean([r["parsed_value"] for r in by_seg_q[(seg, qid)]]) for seg in segments]
        max_v = max((m for m in means if m), default=100)
        vmax  = round(max_v * 1.25 / 500) * 500 or 500
        chart_html = svg_vbar(segments, means, vmin=0, vmax=vmax, y_suffix="")
        title = qtext[:90] + " (NT$)"

    # ── Binary ──
    elif qtype == "binary":
        pcts = []
        for seg in segments:
            vals = [r["parsed_value"] for r in by_seg_q[(seg, qid)]]
            pcts.append(round(100 * sum(1 for v in vals if v == "1") / len(vals), 1) if vals else 0)
        chart_html = svg_vbar(segments, pcts, vmin=0, vmax=100, y_suffix="%")
        title = qtext[:90]

    # ── Multi-select ──
    elif qtype == "multi_select":
        options = meta.get("options") or []
        if not options:
            all_opts = []
            for seg in segments:
                for r in by_seg_q[(seg, qid)]:
                    all_opts.extend(parse_ms(r["parsed_value"]))
            options = list(dict.fromkeys(all_opts))
        matrix = []
        for opt in options:
            row = []
            for seg in segments:
                vals = [r["parsed_value"] for r in by_seg_q[(seg, qid)]]
                n = len(vals)
                count = sum(1 for v in vals if opt in parse_ms(v))
                row.append(round(100 * count / n, 1) if n else 0)
            matrix.append(row)
        chart_html = svg_heatmap(options, segments, matrix)
        title = qtext[:90]

    # ── Open ──
    else:
        quotes = []
        for seg, color in zip(segments, SEG_COLORS):
            cell = by_seg_q[(seg, qid)]
            sample = cell[0]["raw_response"][:160] if cell else "—"
            quotes.append(f'<div style="margin-bottom:8px">'
                          f'<span style="font-size:9px;font-weight:bold;color:{color}">{esc(seg)}</span><br>'
                          f'<span style="color:#555;font-size:11px">&ldquo;{esc(sample)}&hellip;&rdquo;</span></div>')
        chart_html = "".join(quotes)
        title = qtext[:90]

    card = (f'<div class="chart-card">'
            f'<div class="chart-title">{esc(title)}</div>'
            f'{chart_html}'
            f'</div>')
    chart_cards.append(card)

chart_grid_html = "\n".join(chart_cards)

# ---------------------------------------------------------------------------
# SDB gap chart
# ---------------------------------------------------------------------------
sdb_chart_html = ""
for pair_base, (aq, nq) in sdb_pairs.items():
    seg_gaps = []
    for seg in segments:
        a = mean([r["parsed_value"] for r in by_seg_q[(seg, aq)]])
        n = mean([r["parsed_value"] for r in by_seg_q[(seg, nq)]])
        seg_gaps.append((seg, round(a - n, 2) if a and n else 0))
    seg_gaps.sort(key=lambda x: -x[1])
    vmax = max(g for _, g in seg_gaps) if seg_gaps else 4
    sdb_chart_html += (f'<h4 style="font-size:11px;color:#666;margin:0 0 6px">'
                       f'{esc(pair_base)} — anonymous minus named (1–5 scale)</h4>')
    sdb_chart_html += svg_sdb_hbar([s for s, _ in seg_gaps], [g for _, g in seg_gaps], vmax=max(vmax, 0.5))

# ---------------------------------------------------------------------------
# Existing raw-response table rows + SDB gap table rows
# ---------------------------------------------------------------------------
def gap_style(gap):
    if gap is None: return ""
    i = min(200, int(abs(gap) / 4 * 200))
    return f"background:rgb(255,{255-i},{255-i})" if gap > 0 else ""

sdb_rows = []
for pair_base, (aq, nq) in sdb_pairs.items():
    sdb_rows.append(f"<tr><th colspan='3' style='background:#c5cae9'>{esc(pair_base)}</th></tr>")
    sdb_rows.append("<tr><th>Segment</th><th>Anon mean</th><th>Named mean → gap</th></tr>")
    for seg in segments:
        a = mean([r["parsed_value"] for r in by_seg_q[(seg, aq)]])
        n = mean([r["parsed_value"] for r in by_seg_q[(seg, nq)]])
        gap = round(a - n, 2) if a and n else None
        bar = "|" * int(abs(gap) * 4) if gap else ""
        sdb_rows.append(f'<tr style="{gap_style(gap)}"><td>{esc(seg)}</td><td>{a}</td>'
                        f'<td>{n} &nbsp; <b>{gap:+.2f}</b> {bar}</td></tr>' if gap is not None
                        else f'<tr><td>{esc(seg)}</td><td>{a}</td><td>{n}</td></tr>')

# Summary table (moved to <details>)
q_summary_rows = []
for qid in questions:
    q_summary_rows.append(f"<tr><th colspan='{len(segments)+1}' style='background:#c5cae9'>{esc(qid)}</th></tr>")
    q_summary_rows.append("<tr><td><b>metric</b></td>" +
                          "".join(f"<td><b>{esc(s)}</b></td>" for s in segments) + "</tr>")
    all_vals = [r["parsed_value"] for r in by_seg_q.get((segments[0], qid), [])]
    if is_numeric(all_vals):
        cells = [f"<td>{mean([r['parsed_value'] for r in by_seg_q[(seg, qid)]])}</td>"
                 for seg in segments]
        q_summary_rows.append("<tr><td>mean</td>" + "".join(cells) + "</tr>")
    else:
        for seg in segments:
            cell = by_seg_q[(seg, qid)]
            sample = esc(cell[0]["raw_response"][:100]) if cell else "—"
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

# ---------------------------------------------------------------------------
# Agent 2 block
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Survey Design section (from report JSON)
# ---------------------------------------------------------------------------
TYPE_COLORS = {
    "likert5":     ("#fef9c3", "#a16207"),
    "binary":      ("#dcfce7", "#166534"),
    "wtp":         ("#fce7f3", "#9d174d"),
    "open":        ("#e0e7ff", "#3730a3"),
    "multi_select":("#dbeafe", "#1e40af"),
}

survey_design_html = ""
segments_html = ""

if REPORT and "questions" in REPORT:
    q_cards = []
    for q in REPORT["questions"]:
        qtype = q.get("type", "likert5")
        bg, fg = TYPE_COLORS.get(qtype, ("#f0f2f5", "#333"))
        cond = q.get("condition", "neutral")
        cond_pill = ""
        if cond == "anonymous":
            cond_pill = ' <span style="background:#fde68a;color:#92400e;padding:1px 7px;border-radius:10px;font-size:9px;font-weight:bold">ANONYMOUS</span>'
        elif cond == "named":
            cond_pill = ' <span style="background:#bfdbfe;color:#1e40af;padding:1px 7px;border-radius:10px;font-size:9px;font-weight:bold">NAMED</span>'
        badge = f'<span style="background:{bg};color:{fg};padding:2px 8px;border-radius:10px;font-size:9px;font-weight:bold">{esc(qtype.upper())}</span>'
        scale = f'<div style="color:#888;font-size:10px;margin-top:4px">{esc(q.get("scale_label",""))}</div>' if q.get("scale_label") else ""
        opts = q.get("options", [])
        opts_html = ""
        if opts:
            letters = [chr(ord("A") + i) for i in range(len(opts))]
            opts_html = '<div style="margin-top:6px;display:flex;flex-wrap:wrap;gap:4px">' + \
                "".join(f'<span style="background:#f1f5f9;border:1px solid #cbd5e1;border-radius:4px;padding:2px 7px;font-size:9px">'
                        f'<b>{l}</b> {esc(o)}</span>' for l, o in zip(letters, opts)) + "</div>"
        q_cards.append(
            f'<div style="background:#fff;border:1px solid #e2e8f0;border-radius:6px;padding:10px 14px;margin-bottom:8px">'
            f'<div style="margin-bottom:6px">{badge}{cond_pill} &nbsp;<code style="font-size:10px;color:#94a3b8">{esc(q["id"])}</code></div>'
            f'<div style="font-size:.85rem;color:#1e293b;font-weight:500">{esc(q["text"])}</div>'
            f'{scale}{opts_html}'
            f'</div>'
        )
    survey_design_html = "\n".join(q_cards)

if REPORT and "segments" in REPORT:
    seg_cards = []
    for i, s in enumerate(REPORT["segments"]):
        color = SEG_COLORS[i % len(SEG_COLORS)]
        w = s.get("weight", 0)
        bar_w = int(w * 200)
        desc = s.get("description", "")
        rationale = s.get("rationale", "")
        seg_cards.append(
            f'<div style="background:#fff;border:1px solid #e2e8f0;border-radius:6px;padding:12px 14px;margin-bottom:8px">'
            f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">'
            f'<span style="width:12px;height:12px;background:{color};border-radius:50%;display:inline-block"></span>'
            f'<b style="font-size:.9rem">{esc(s["name"])}</b>'
            f'<span style="font-size:.8rem;color:#64748b">weight: {w:.0%}</span>'
            f'</div>'
            f'<div style="background:#e2e8f0;border-radius:4px;height:6px;margin-bottom:8px">'
            f'<div style="background:{color};width:{bar_w}px;height:6px;border-radius:4px;opacity:.8"></div></div>'
            f'<div style="font-size:.78rem;color:#475569;margin-bottom:4px"><b>Persona:</b> {esc(desc)}</div>'
            f'<div style="font-size:.75rem;color:#94a3b8"><b>Rationale:</b> {esc(rationale)}</div>'
            f'</div>'
        )
    segments_html = "\n".join(seg_cards)

# ---------------------------------------------------------------------------
# Sanity check tables
# ---------------------------------------------------------------------------
PASS_STYLE  = "background:#dcfce7;color:#166534;font-weight:bold"
FAIL_STYLE  = "background:#fee2e2;color:#991b1b;font-weight:bold"

sanity_rows_consistency = []
for prefix, (v1id, v2id) in consistency_pairs.items():
    sanity_rows_consistency.append(
        f"<tr><th colspan='{len(segments)+4}' style='background:#c5cae9'>"
        f"Consistency: {esc(prefix)} ({esc(v1id)} vs {esc(v2id)})</th></tr>"
    )
    sanity_rows_consistency.append(
        "<tr><th>Segment</th><th>v1 mean</th><th>v2 mean</th>"
        "<th>Gap (v1−v2)</th><th>Status (≤ 0.5)</th></tr>"
    )
    for seg in segments:
        m1 = mean([r["parsed_value"] for r in by_seg_q[(seg, v1id)]])
        m2 = mean([r["parsed_value"] for r in by_seg_q[(seg, v2id)]])
        if m1 is not None and m2 is not None:
            gap = round(m1 - m2, 2)
            passed = abs(gap) <= 0.5
            style = PASS_STYLE if passed else FAIL_STYLE
            status = "✓ PASS" if passed else "✗ FAIL"
            sanity_rows_consistency.append(
                f'<tr><td>{esc(seg)}</td><td>{m1}</td><td>{m2}</td>'
                f'<td>{gap:+.2f}</td><td style="{style}">{status}</td></tr>'
            )
        else:
            sanity_rows_consistency.append(
                f'<tr><td>{esc(seg)}</td><td>{m1}</td><td>{m2}</td>'
                f'<td>—</td><td>—</td></tr>'
            )

sanity_rows_reverse = []
for prefix, (pid, nid) in reverse_pairs.items():
    sanity_rows_reverse.append(
        f"<tr><th colspan='{len(segments)+4}' style='background:#c5cae9'>"
        f"Reverse-coded: {esc(prefix)} ({esc(pid)} + {esc(nid)})</th></tr>"
    )
    sanity_rows_reverse.append(
        "<tr><th>Segment</th><th>pos mean</th><th>neg mean</th>"
        "<th>Sum (target ≈ 6)</th><th>Status (6.0 ± 1.0)</th></tr>"
    )
    for seg in segments:
        mp = mean([r["parsed_value"] for r in by_seg_q[(seg, pid)]])
        mn = mean([r["parsed_value"] for r in by_seg_q[(seg, nid)]])
        if mp is not None and mn is not None:
            total = round(mp + mn, 2)
            passed = abs(total - 6.0) <= 1.0
            style = PASS_STYLE if passed else FAIL_STYLE
            status = "✓ PASS" if passed else "✗ FAIL"
            sanity_rows_reverse.append(
                f'<tr><td>{esc(seg)}</td><td>{mp}</td><td>{mn}</td>'
                f'<td>{total:.2f}</td><td style="{style}">{status}</td></tr>'
            )
        else:
            sanity_rows_reverse.append(
                f'<tr><td>{esc(seg)}</td><td>{mp}</td><td>{mn}</td>'
                f'<td>—</td><td>—</td></tr>'
            )

sanity_section_html = ""
if sanity_rows_consistency or sanity_rows_reverse:
    rows_html_inner = "".join(sanity_rows_consistency + sanity_rows_reverse)
    sanity_section_html = f"""<section id="s-sanity">
<h2>Sanity Checks &mdash; Response Consistency</h2>
<div class="section">
<p style="font-size:.8rem;color:#64748b;margin-bottom:12px">
  <b>Consistency pair</b> (gap ≤ 0.5 = PASS): same construct, two wordings — means should match.<br>
  <b>Reverse-coded pair</b> (sum ≈ 6.0 ± 1.0 = PASS): pos + neg question — coherent respondents sum near 6 on 1–5 scale.
</p>
<table><tbody>{rows_html_inner}</tbody></table>
</div>
</section>"""

# ---------------------------------------------------------------------------
# Dynamic title
# ---------------------------------------------------------------------------
_title_text = "Prism Report"
if REPORT and "input_text" in REPORT:
    _title_text = REPORT["input_text"][:60]
elif REPORT and "segments" in REPORT and REPORT["segments"]:
    _title_text = f"Study — {REPORT['segments'][0].get('name','')}"

# ---------------------------------------------------------------------------
# Agent 2 block
# ---------------------------------------------------------------------------
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
    agent2_block = f"""<section id="s-agent2">
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
  <table><thead><tr><th>Risk Flags</th></tr></thead><tbody>{flags}</tbody></table>
</div>
</section>"""
    toc_agent2 = '<a href="#s-agent2">Agent 2 Analysis</a>'
else:
    agent2_block = ""
    toc_agent2   = '<a style="opacity:.4">Agent 2 (no report.json)</a>'

toc_segs = "".join(
    f'<a href="#s-raw" class="toc-filter" data-seg="{esc(s)}">{esc(s)}</a>'
    for s in segments)
toc_qs = "".join(
    f'<a href="#s-raw" class="toc-filter" data-q="{esc(q)}">{esc(q)}</a>'
    for q in questions)

# ---------------------------------------------------------------------------
# Write HTML
# ---------------------------------------------------------------------------
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Prism Report — {esc(JSONL.name)}</title>
<style>
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family:system-ui,sans-serif; background:#f0f2f5; color:#222;
        display:flex; flex-direction:column; height:100vh; overflow:hidden; }}
#topbar {{ background:#1a1a2e; color:#eee; padding:10px 18px;
           font-size:.95rem; font-weight:bold; flex-shrink:0; }}
#layout {{ display:flex; flex:1; overflow:hidden; }}

/* Sidebar */
#toc {{ width:210px; min-width:210px; background:#1e2a3a; color:#aac;
        overflow-y:auto; padding-bottom:20px; flex-shrink:0; }}
#toc .toc-label {{ padding:10px 14px 4px; font-size:.68rem;
                   text-transform:uppercase; color:#556; letter-spacing:.08em; }}
#toc a {{ display:block; padding:6px 14px; color:#8ab; text-decoration:none;
           font-size:.8rem; border-left:3px solid transparent;
           white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
#toc a:hover {{ background:#243447; color:#fff; border-left-color:#5b8dee; }}
#toc a.active {{ background:#1a3050; color:#fff; border-left-color:#5b8dee; }}

/* Main */
#main {{ flex:1; overflow-y:auto; overflow-x:hidden; }}
section {{ scroll-margin-top:4px; }}
h2 {{ background:#16213e; color:#ccc; padding:9px 18px; font-size:.9rem;
      position:sticky; top:0; z-index:10; }}
.section {{ padding:14px 18px; }}

/* Tables */
table {{ border-collapse:collapse; width:100%; font-size:.82rem; background:#fff; }}
th, td {{ border:1px solid #ddd; padding:5px 9px; text-align:left; vertical-align:top; }}
th {{ background:#e8eaf6; }}
tr:hover td {{ background:#f0f4ff; }}

/* Chart grid */
.chart-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(380px,1fr)); gap:14px; }}
.chart-card {{ background:#fff; border:1px solid #ddd; border-radius:6px; padding:12px 14px; }}
.chart-title {{ font-size:.78rem; color:#475569; margin-bottom:8px; line-height:1.4; font-weight:bold; }}

/* Details */
details {{ margin:0; }}
details summary {{ cursor:pointer; padding:8px 18px;
                   background:#eef; font-size:.83rem; color:#336; }}

/* Raw controls */
.controls {{ padding:8px 18px; background:#fff; border-bottom:1px solid #ddd;
             display:flex; gap:10px; align-items:center; flex-wrap:wrap;
             position:sticky; top:34px; z-index:9; }}
select, input {{ padding:4px 8px; border:1px solid #bbb; border-radius:4px; font-size:.85rem; }}
.count {{ font-size:.8rem; color:#666; }}
</style>
</head>
<body>
<div id="topbar">Prism &mdash; {esc(_title_text)} &nbsp;|&nbsp; {esc(JSONL.name)} &nbsp;|&nbsp; {len(rows)} responses</div>
<div id="layout">
<nav id="toc">
  <div class="toc-label">Sections</div>
  {toc_agent2}
  <a href="#s-segments">Segments</a>
  <a href="#s-survey">Survey Design</a>
  <a href="#s-sdb">SDB Gaps</a>
  <a href="#s-sanity">Sanity Checks</a>
  <a href="#s-viz">Visualizations</a>
  <a href="#s-raw">Raw Responses</a>
  <div class="toc-label">Filter by Segment</div>
  {toc_segs}
  <div class="toc-label">Filter by Question</div>
  {toc_qs}
</nav>
<div id="main">

{agent2_block}

{'<section id="s-segments"><h2>Audience Segments</h2><div class="section">' + segments_html + '</div></section>' if segments_html else ''}

{'<section id="s-survey"><h2>Survey Design — Agent 1 Output</h2><div class="section">' + survey_design_html + '</div></section>' if survey_design_html else ''}

<section id="s-sdb">
<h2>SDB Gaps &mdash; Anonymous vs Named Disclosure</h2>
<div class="section">
{sdb_chart_html}
<details style="margin-top:12px">
  <summary>Show data table</summary>
  <table><tbody>{''.join(sdb_rows)}</tbody></table>
</details>
</div>
</section>

{sanity_section_html}

<section id="s-viz">
<h2>Visualizations &mdash; Per-Question Segment Comparison</h2>
<div class="section">
<div class="chart-grid">
{chart_grid_html}
</div>
<details style="margin-top:14px">
  <summary>Show summary data table</summary>
  <div style="overflow-x:auto">
  <table>
    <thead><tr><th>Question / Metric</th>{''.join(f'<th>{esc(s)}</th>' for s in segments)}</tr></thead>
    <tbody>{''.join(q_summary_rows)}</tbody>
  </table>
  </div>
</details>
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
<div class="section" style="padding-top:0;overflow-x:auto">
<table>
  <thead><tr><th>Segment</th><th>Question</th><th>Raw Response</th><th>Parsed</th></tr></thead>
  <tbody>{''.join(rows_html)}</tbody>
</table>
</div>
</section>

</div>
</div>
<script>
const segF=document.getElementById('seg-filter'),qF=document.getElementById('q-filter'),
      srch=document.getElementById('search'),countEl=document.getElementById('count'),
      allRows=Array.from(document.querySelectorAll('.r-row'));
function filter(){{
  const seg=segF.value,q=qF.value,kw=srch.value.toLowerCase();
  let n=0;
  allRows.forEach(row=>{{
    const show=(!seg||row.dataset.seg===seg)&&(!q||row.dataset.q===q)
               &&(!kw||row.textContent.toLowerCase().includes(kw));
    row.style.display=show?'':'none'; if(show)n++;
  }});
  countEl.textContent=n+' shown';
}}
segF.addEventListener('change',filter);qF.addEventListener('change',filter);
srch.addEventListener('input',filter);
document.querySelectorAll('.toc-filter').forEach(a=>{{
  a.addEventListener('click',e=>{{
    e.preventDefault();
    if(a.dataset.seg)segF.value=a.dataset.seg;
    if(a.dataset.q)qF.value=a.dataset.q;
    filter();
    document.getElementById('s-raw').scrollIntoView({{behavior:'smooth'}});
  }});
}});
const sections=document.querySelectorAll('section[id]'),
      tocLinks=document.querySelectorAll('#toc a[href^="#s-"]');
const obs=new IntersectionObserver(entries=>{{
  entries.forEach(e=>{{
    if(e.isIntersecting){{
      tocLinks.forEach(l=>l.classList.remove('active'));
      const a=document.querySelector('#toc a[href="#'+e.target.id+'"]');
      if(a)a.classList.add('active');
    }}
  }});
}},{{root:document.getElementById('main'),threshold:0.2}});
sections.forEach(s=>obs.observe(s));
</script>
</body>
</html>"""

HTML.write_text(html, encoding="utf-8")
print(f"HTML written -> {HTML}")
