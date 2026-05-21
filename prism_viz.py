"""
prism_viz.py — shared visualization helpers for Prism.
SVG generators (used by prism_report.py offline HTML).
Plotly builders (used by prism_app.py Streamlit).
"""

# ---------------------------------------------------------------------------
# SVG helpers (verbatim from prism_report.py)
# ---------------------------------------------------------------------------

SEG_COLORS = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f", "#b07aa1"]


def _p(n):
    return f"{round(float(n), 1)}"


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


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
    HIST_C = ["#e15759", "#f28e2b", "#edc948", "#76b7b2", "#59a14f"]
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


# ---------------------------------------------------------------------------
# Plotly helpers (used by prism_app.py)
# ---------------------------------------------------------------------------

import plotly.express as px
import plotly.graph_objects as go


def plotly_segment_bar(seg_labels, values, title, y_label, vmin=None, vmax=None, colors=None):
    """Vertical bar per segment, Plotly. Returns fig."""
    if colors is None:
        colors = SEG_COLORS[:len(seg_labels)]
    fig = go.Figure(
        go.Bar(
            x=seg_labels,
            y=values,
            marker_color=colors[:len(seg_labels)],
            text=[f"{v:.2f}" if v is not None else "" for v in values],
            textposition="outside",
        )
    )
    fig.update_layout(
        title=title,
        yaxis_title=y_label,
        showlegend=False,
        height=350,
        margin=dict(t=50, b=40, l=40, r=10),
    )
    if vmin is not None or vmax is not None:
        fig.update_yaxes(range=[vmin, vmax])
    return fig


def plotly_grouped_bar(seg_labels, anon_vals, named_vals, title):
    """Two-series grouped bar anon/named per segment. Returns fig."""
    fig = go.Figure([
        go.Bar(
            name="Anonymous",
            x=seg_labels,
            y=anon_vals,
            marker_color="#f28e2b",
            text=[f"{v:.2f}" if v is not None else "" for v in anon_vals],
            textposition="outside",
        ),
        go.Bar(
            name="Named",
            x=seg_labels,
            y=named_vals,
            marker_color="#4e79a7",
            text=[f"{v:.2f}" if v is not None else "" for v in named_vals],
            textposition="outside",
        ),
    ])
    fig.update_layout(
        title=title,
        barmode="group",
        yaxis_title="Mean score (1–5)",
        height=350,
        margin=dict(t=50, b=40, l=40, r=10),
        yaxis=dict(range=[1, 5]),
    )
    return fig


def plotly_pie(seg_labels, weights, title="Segment Weights"):
    """Donut pie chart. Returns fig."""
    fig = go.Figure(
        go.Pie(
            labels=seg_labels,
            values=weights,
            hole=0.4,
            marker_colors=SEG_COLORS[:len(seg_labels)],
            textinfo="percent+label",
            textposition="inside",
        )
    )
    fig.update_layout(
        title=title,
        height=350,
        margin=dict(t=50, b=10, l=10, r=10),
        showlegend=False,
    )
    return fig


def plotly_heatmap(row_labels, col_labels, matrix, title):
    """Multi-select heatmap %. Returns fig."""
    fig = go.Figure(
        go.Heatmap(
            z=matrix,
            x=col_labels,
            y=row_labels,
            colorscale="Blues",
            text=[[f"{v:.1f}%" if v is not None else "" for v in row] for row in matrix],
            texttemplate="%{text}",
            showscale=True,
            zmin=0,
            zmax=100,
        )
    )
    fig.update_layout(
        title=title,
        height=max(250, 40 * len(row_labels) + 80),
        margin=dict(t=50, b=40, l=160, r=10),
        yaxis=dict(autorange="reversed"),
    )
    return fig
