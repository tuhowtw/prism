"""
SSR unit smoke test — prism_ssr_test.py
Run: python prism_ssr_test.py

Verifies _ssr_score maps clearly negative/neutral/positive free-text responses
to expected Likert positions. Requires OPENAI_API_KEY in env.
"""
import asyncio
from prism_engine import _ssr_score, _GENERIC_ANCHORS_AGREEMENT

ANCHORS = _GENERIC_ANCHORS_AGREEMENT

CASES = [
    ("I completely oppose this and think it's a terrible idea.", 1, 2.5),
    ("I have no strong feelings either way about this.", 2.5, 3.5),
    ("I fully support this and think it's an excellent idea.", 3.5, 5),
]

async def main():
    print("SSR Unit Smoke Test")
    print("=" * 60)
    print(f"Anchors:\n" + "\n".join(f"  {i+1}: {a}" for i, a in enumerate(ANCHORS)))
    print()

    all_pass = True
    for text, ev_min, ev_max in CASES:
        pmf, ev = await _ssr_score(text, ANCHORS)
        peak = pmf.index(max(pmf)) + 1
        ok = ev_min <= ev <= ev_max
        status = "OK" if ok else "FAIL"
        print(f"[{status}] EV={ev:.2f} (expected {ev_min}–{ev_max}), peak={peak}")
        print(f"       pmf={[round(p, 3) for p in pmf]}")
        print(f"       text: \"{text[:70]}\"")
        if not ok:
            all_pass = False
        print()

    print("=" * 60)
    print("PASS" if all_pass else "FAIL — check anchor quality or embedding model")

asyncio.run(main())
