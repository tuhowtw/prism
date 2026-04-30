from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup


RIS_TABLE11_URL = "https://www.ris.gov.tw/documents/data/en/3/Table11-y2024.xls"
WORLDBANK_TFR_URL = "https://api.worldbank.org/v2/country/JPN;KOR/indicator/SP.DYN.TFRT.IN?format=json&per_page=200"

RAG_SOURCE_URLS = [
    "https://www.ris.gov.tw/app/en/3910",
    "https://eng.stat.gov.tw/cl.aspx?n=2437",
    "https://www.e-stat.go.jp/en/developer",
    "https://kosis.kr/eng/statisticsList/statisticsListIndex.do?vwcd=MT_ETITLE&menuId=M_01_01",
    "https://www.oecd.org/en/data/indicators/fertility-rates.html",
]


def _clean_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def fetch_taiwan_table11_yearly(url: str = RIS_TABLE11_URL) -> pd.DataFrame:
    """Parse Taiwan Table 11 (RIS) to yearly Grand Total fertility metrics."""
    workbook = pd.ExcelFile(url)
    rows: list[dict[str, float | int]] = []

    for sheet in workbook.sheet_names:
        year_match = re.search(r"\d{4}", sheet)
        if not year_match:
            continue
        year = int(year_match.group(0))

        df = pd.read_excel(url, sheet_name=sheet, header=None)
        label_col = df[0].astype(str)
        grand_total = df[label_col.str.contains(r"Grand\s*Total|總\s*計", case=False, na=False)]
        if grand_total.empty:
            continue

        row = grand_total.iloc[0]
        crude_birth_rate = pd.to_numeric(row.iloc[1], errors="coerce")
        general_fertility_rate = pd.to_numeric(row.iloc[2], errors="coerce")
        tfr_per_thousand = pd.to_numeric(row.iloc[10], errors="coerce")
        if pd.isna(tfr_per_thousand):
            continue

        rows.append(
            {
                "country": "TWN",
                "country_name": "Taiwan",
                "year": year,
                "crude_birth_rate_per_thousand_population": float(crude_birth_rate)
                if not pd.isna(crude_birth_rate)
                else None,
                "general_fertility_rate_per_thousand_women": float(general_fertility_rate)
                if not pd.isna(general_fertility_rate)
                else None,
                "tfr_per_thousand_women": float(tfr_per_thousand),
                "tfr_births_per_woman": float(tfr_per_thousand) / 1000.0,
                "source": url,
            }
        )

    return pd.DataFrame(rows).sort_values("year").reset_index(drop=True)


def fetch_worldbank_jpn_kor(url: str = WORLDBANK_TFR_URL) -> pd.DataFrame:
    """Fetch Japan and Korea TFR from World Bank API."""
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    payload = response.json()

    data = payload[1] if isinstance(payload, list) and len(payload) > 1 else []
    rows: list[dict[str, object]] = []
    for item in data:
        year_raw = item.get("date")
        value = item.get("value")
        iso3 = item.get("countryiso3code")
        if value is None or iso3 not in {"JPN", "KOR"}:
            continue
        if not str(year_raw).isdigit():
            continue
        rows.append(
            {
                "country": iso3,
                "country_name": item.get("country", {}).get("value", iso3),
                "year": int(year_raw),
                "tfr_births_per_woman": float(value),
                "source": url,
            }
        )

    return pd.DataFrame(rows).sort_values(["country", "year"]).reset_index(drop=True)


def fetch_rag_docs(urls: list[str] | None = None, max_chars: int = 1500) -> list[dict[str, str]]:
    """Collect short text snippets from policy/statistics pages for RAG retrieval demo."""
    urls = urls or RAG_SOURCE_URLS
    docs: list[dict[str, str]] = []

    for url in urls:
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")
            title = _clean_spaces(soup.title.get_text()) if soup.title else url
            text = _clean_spaces(soup.get_text(" ", strip=True))
            snippet = text[:max_chars]
            if len(snippet) < 200:
                continue
            docs.append({"title": title, "url": url, "text": snippet})
        except Exception:
            continue

    return docs


def build_snapshot() -> dict[str, object]:
    tw_df = fetch_taiwan_table11_yearly()
    wb_df = fetch_worldbank_jpn_kor()
    rag_docs = fetch_rag_docs()

    panel_df = pd.concat(
        [
            tw_df[["country", "country_name", "year", "tfr_births_per_woman", "source"]],
            wb_df[["country", "country_name", "year", "tfr_births_per_woman", "source"]],
        ],
        ignore_index=True,
    ).sort_values(["country", "year"]).reset_index(drop=True)

    latest = (
        panel_df.dropna(subset=["tfr_births_per_woman"]) 
        .sort_values("year")
        .groupby("country", as_index=False)
        .tail(1)
    )
    latest_dict = {
        r["country"]: {
            "country_name": r["country_name"],
            "year": int(r["year"]),
            "tfr": float(r["tfr_births_per_woman"]),
        }
        for _, r in latest.iterrows()
    }

    return {
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "sources": {
            "taiwan_table11": RIS_TABLE11_URL,
            "worldbank_jpn_kor": WORLDBANK_TFR_URL,
            "rag_urls": RAG_SOURCE_URLS,
        },
        "summary": {
            "records_panel": int(len(panel_df)),
            "countries": sorted(panel_df["country"].unique().tolist()),
            "latest_tfr": latest_dict,
            "rag_docs_count": len(rag_docs),
        },
        "taiwan_table11_yearly": tw_df.to_dict(orient="records"),
        "east_asia_panel": panel_df.to_dict(orient="records"),
        "rag_docs": rag_docs,
    }


def save_snapshot(output_dir: str = "data") -> dict[str, Path]:
    payload = build_snapshot()

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    tw_df = pd.DataFrame(payload["taiwan_table11_yearly"])
    panel_df = pd.DataFrame(payload["east_asia_panel"])

    tw_path = out_dir / "fertility_taiwan_table11_yearly.csv"
    panel_path = out_dir / "fertility_east_asia_panel.csv"
    docs_path = out_dir / "fertility_rag_docs.json"
    snapshot_path = out_dir / "fertility_mvp_snapshot.json"

    tw_df.to_csv(tw_path, index=False)
    panel_df.to_csv(panel_path, index=False)
    docs_path.write_text(json.dumps(payload["rag_docs"], ensure_ascii=False, indent=2), encoding="utf-8")
    snapshot_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "taiwan_csv": tw_path,
        "panel_csv": panel_path,
        "rag_docs_json": docs_path,
        "snapshot_json": snapshot_path,
    }


if __name__ == "__main__":
    paths = save_snapshot(output_dir="data")
    print("Saved:")
    for key, value in paths.items():
        print(f"- {key}: {value}")
