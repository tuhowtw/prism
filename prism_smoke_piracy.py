"""
Prism Smoke Test — Piracy SDB Study
Run: python prism_smoke_piracy.py

Tests extended pipeline end-to-end on the piracy implicit-preferences research question.
Verifies: multi_select questions, anonymous/named condition framing, SDB gap computation.
Keep RESPONSES_PER_CELL small (3) to minimize cost during smoke.
"""
from prism_engine import run_agent1_propose, run_simulation, _aggregate_responses, run_agent2

INPUT = (
    "Research study on digital piracy implicit preferences in Taiwan. "
    "Goal: measure how frequency, drivers, moral attitudes, and willingness-to-pay "
    "for legal alternatives differ across socioeconomic segments, and quantify the "
    "social-desirability bias (SDB) gap between anonymous and named disclosure conditions. "
    "Domains: streaming services, ebooks, software, music. "
    "Target stakeholders: urban white-collar workers, university students, "
    "middle-aged parents, blue-collar workers."
)

RESPONSES_PER_CELL = 20

print("=" * 70)
print("PRISM — PIRACY SDB SMOKE TEST")
print("=" * 70)
print(f"\nInput:\n  {INPUT[:120]}...\n")

# Stage 1: Agent 1
print("[1/4] Agent 1: generating segments and questions...")
segments, questions = run_agent1_propose(INPUT)
print(f"      → {len(segments)} segments, {len(questions)} questions\n")

for s in segments:
    print(f"  Segment: {s.name} (weight={s.weight:.0%})")
    print(f"           {s.rationale[:80]}")
print()

# Check schema requirements
anon_qs = [q for q in questions if q.condition == "anonymous"]
named_qs = [q for q in questions if q.condition == "named"]
multi_qs = [q for q in questions if q.type == "multi_select"]
open_qs  = [q for q in questions if q.type == "open"]

print("  Question inventory:")
for q in questions:
    cond_tag = f" [{q.condition}]" if q.condition != "neutral" else ""
    print(f"    [{q.id}] ({q.type}){cond_tag}  {q.text[:70]}")
print()
print(f"  Schema checks:")
print(f"    [OK] Question count: {len(questions)} {'OK' if 12 <= len(questions) <= 15 else 'WARN: outside 12-15 range'}")
print(f"    {'[OK]' if anon_qs else '[!!]'} Anonymous condition Qs: {[q.id for q in anon_qs]}")
print(f"    {'[OK]' if named_qs else '[!!]'} Named condition Qs:     {[q.id for q in named_qs]}")
print(f"    {'[OK]' if multi_qs else '[!!]'} Multi-select Qs:        {[q.id for q in multi_qs]}")
print(f"    {'[OK]' if open_qs else '[!!]'} Open-ended Qs:          {[q.id for q in open_qs]}")
print()

# Stage 2: Simulation
total_calls = len(segments) * len(questions) * RESPONSES_PER_CELL
print(f"[2/4] Simulation: {len(segments)} seg × {len(questions)} Q × {RESPONSES_PER_CELL} resp = {total_calls} calls...")
responses = run_simulation(segments, questions, responses_per_cell=RESPONSES_PER_CELL, max_concurrent=5)
print(f"      → {len(responses)} responses collected\n")

import json as _json, datetime as _dt, pathlib as _pl
_runs_dir = _pl.Path("runs")
_runs_dir.mkdir(exist_ok=True)
_ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
_run_file = _runs_dir / f"{_ts}_n{RESPONSES_PER_CELL}.jsonl"
with open(_run_file, "w", encoding="utf-8") as _f:
    for r in responses:
        _f.write(_json.dumps({
            "segment": r.segment_name,
            "question_id": r.question_id,
            "raw_response": r.raw_response,
            "parsed_value": str(r.parsed_value),
            "pmf": r.pmf,
        }) + "\n")
print(f"      Raw responses saved → {_run_file}\n")

# Stage 3: Aggregation
print("[3/4] Aggregating results...")
seg_results = _aggregate_responses(responses, segments, questions)
print()

for sr in seg_results:
    print(f"  Segment: {sr.segment.name}")
    for qid, stats in sr.question_summaries.items():
        if qid == "__sdb_gaps__":
            for pair_prefix, gap in stats.items():
                direction = "↑ hides when named" if gap > 0 else "↓ less anonymous effect"
                print(f"    [SDB gap: {pair_prefix}]  anon−named = {gap:+.2f}  {direction}")
        elif stats["type"] == "likert5":
            cond = stats.get("condition", "neutral")
            cond_tag = f" [{cond}]" if cond != "neutral" else ""
            print(f"    [{qid}]{cond_tag}  mean={stats['mean']}/5 (n={stats['n']})")
        elif stats["type"] == "binary":
            print(f"    [{qid}]  {stats['pct_yes']}% yes (n={stats['n']})")
        elif stats["type"] == "wtp":
            print(f"    [{qid}]  mean WTP=NT${stats['mean']} (n={stats['n']})")
        elif stats["type"] == "multi_select":
            top = sorted(stats["rates"].items(), key=lambda x: -x[1])[:3]
            print(f"    [{qid}]  top drivers: {', '.join(f'{o}: {r}%' for o, r in top)}")
    if sr.open_themes:
        print(f"    [open]  \"{sr.open_themes[0][:100]}\"")
    print()

# SDB gap summary across all segments
all_gaps: dict[str, list[tuple[str, float]]] = {}
for sr in seg_results:
    gaps = sr.question_summaries.get("__sdb_gaps__", {})
    for pair_prefix, gap in gaps.items():
        all_gaps.setdefault(pair_prefix, []).append((sr.segment.name, gap))

if all_gaps:
    print("  SDB Gap Summary (anon − named; positive = higher disclosure when anonymous):")
    for pair_prefix, seg_gaps in all_gaps.items():
        print(f"  Pair: {pair_prefix}")
        for seg_name, gap in sorted(seg_gaps, key=lambda x: -x[1]):
            bar = "|" * int(abs(gap) * 4)
            print(f"    {seg_name:<30} {gap:+.2f}  {bar}")
    print()
else:
    print("  (!) No SDB pairs detected in aggregation. Check question id naming (_anon/_named).\n")

# Stage 4: Agent 2
print("[4/4] Agent 2: generating strategic recommendations...")
output = run_agent2(seg_results, questions, INPUT)

print(f"\n  Overall reception score: {output.overall_summary.get('weighted_reception_score')}/5")
print(f"  Key insight: {output.overall_summary.get('key_insight')}")
print(f"  Target segment: {output.target_segment}")
print("\n  Recommendations:")
for i, r in enumerate(output.recommendations, 1):
    print(f"    {i}. {r}")
print("\n  Risk flags:")
for f in output.risk_flags:
    print(f"    (!) {f}")

# Save Agent 2 report alongside the run file
_report = {
    "run_file": str(_run_file),
    "timestamp": _ts,
    "n_per_cell": RESPONSES_PER_CELL,
    "input_text": INPUT,
    "segments": [
        {"name": s.name, "weight": s.weight, "description": s.description, "rationale": s.rationale}
        for s in segments
    ],
    "questions": [
        {"id": q.id, "text": q.text, "type": q.type, "condition": q.condition,
         "scale_label": q.scale_label, "options": q.options}
        for q in questions
    ],
    "sdb_gaps": {
        pair_prefix: {seg_name: gap for seg_name, gap in seg_gaps}
        for pair_prefix, seg_gaps in all_gaps.items()
    },
    "segment_stats": {
        sr.segment.name: {
            qid: stats for qid, stats in sr.question_summaries.items()
        }
        for sr in seg_results
    },
    "agent2": {
        "overall_summary": output.overall_summary,
        "target_segment": output.target_segment,
        "recommendations": output.recommendations,
        "risk_flags": output.risk_flags,
    },
}
_report_file = _runs_dir / f"{_ts}_n{RESPONSES_PER_CELL}_report.json"
with open(_report_file, "w", encoding="utf-8") as _f:
    _json.dump(_report, _f, ensure_ascii=False, indent=2)
print(f"  Report saved → {_report_file}")

print()
print("=" * 70)
print("SMOKE DONE")
print("=" * 70)
