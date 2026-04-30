"""
Prism CLI Test
Run: python prism_cli_test.py

Tests the full pipeline end-to-end with a hardcoded input.
Prints results to terminal — no UI needed.
"""
from prism_engine import run_agent1_propose, run_simulation, _aggregate_responses, run_agent2

INPUT = (
    "A government policy offering NT$200,000 cash subsidy per child for the first two "
    "children, targeted at married couples aged 25-40 in major Taiwan cities. "
    "Means-tested: household income below NT$1.5M/year."
)

RESPONSES_PER_CELL = 5  # keep low for a quick test

print("=" * 60)
print("PRISM — CLI TEST")
print("=" * 60)
print(f"\nInput:\n  {INPUT[:100]}...\n")

print("[1/4] Agent 1: generating segments and questions...")
segments, questions = run_agent1_propose(INPUT)

print(f"      → {len(segments)} segments, {len(questions)} questions\n")
for s in segments:
    print(f"      • {s.name} (weight={s.weight:.0%}) — {s.rationale[:60]}")
print()
for q in questions:
    print(f"      [{q.id}] ({q.type}) {q.text[:70]}")

print(f"\n[2/4] Simulation: {len(segments)} × {len(questions)} × {RESPONSES_PER_CELL} calls...")
responses = run_simulation(segments, questions, responses_per_cell=RESPONSES_PER_CELL)
print(f"      → {len(responses)} responses collected\n")

print("[3/4] Aggregating...")
seg_results = _aggregate_responses(responses, segments, questions)

for sr in seg_results:
    print(f"\n  Segment: {sr.segment.name}")
    for qid, stats in sr.question_summaries.items():
        if stats["type"] == "likert5":
            print(f"    [{qid}] mean={stats['mean']}/5 (n={stats['n']})")
        elif stats["type"] == "binary":
            print(f"    [{qid}] {stats['pct_yes']}% yes (n={stats['n']})")
        elif stats["type"] == "wtp":
            print(f"    [{qid}] mean WTP=NT${stats['mean']} (n={stats['n']})")

print("\n[4/4] Agent 2: generating recommendations...")
output = run_agent2(seg_results, questions, INPUT)

print(f"\n  Overall reception: {output.overall_summary.get('weighted_reception_score')}/5")
print(f"  Key insight: {output.overall_summary.get('key_insight')}")
print(f"  Target segment: {output.target_segment}")
print("\n  Recommendations:")
for i, r in enumerate(output.recommendations, 1):
    print(f"    {i}. {r}")
print("\n  Risk flags:")
for f in output.risk_flags:
    print(f"    ⚠ {f}")

print("\n" + "=" * 60)
print("DONE")
print("=" * 60)
