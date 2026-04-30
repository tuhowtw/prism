from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib3.exceptions import InsecureRequestWarning


requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

FX_FIRST_PAGE_URL = "https://www.cbc.gov.tw/tw/lp-645-1.html"
FX_PAGE_URL_TEMPLATE = "https://www.cbc.gov.tw/tw/lp-645-1-{page}-20.html"
RATE_FEED_URL = "https://www.cbc.gov.tw/public/data/bkrldc.txt"
POLICY_NEWS_URL = "https://www.cbc.gov.tw/tw/np-971-1.html"
CBC_HOME_URL = "https://www.cbc.gov.tw/tw/mp-1.html"


def _get_html(url: str, timeout: int = 30) -> str:
    response = requests.get(url, timeout=timeout, verify=False)
    response.raise_for_status()
    return response.text


def fetch_fx_rates(max_pages: int = 5) -> pd.DataFrame:
    """Scrape recent NTD/USD interbank close rates from CBC pages."""
    rows: list[dict[str, object]] = []

    for page in range(1, max_pages + 1):
        url = FX_FIRST_PAGE_URL if page == 1 else FX_PAGE_URL_TEMPLATE.format(page=page)
        soup = BeautifulSoup(_get_html(url), "lxml")
        table = soup.select_one("table")
        if table is None:
            continue

        for tr in table.select("tr"):
            cells = [td.get_text(strip=True) for td in tr.select("th,td")]
            if len(cells) < 2:
                continue
            date_text, value_text = cells[0], cells[1]
            if not re.match(r"^\d{4}/\d{2}/\d{2}$", date_text):
                continue
            try:
                rate_value = float(value_text)
            except ValueError:
                continue

            rows.append(
                {
                    "date": datetime.strptime(date_text, "%Y/%m/%d").date().isoformat(),
                    "ntd_usd": rate_value,
                    "source_page": page,
                }
            )

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    return df


def fetch_rate_feed_preview(max_lines: int = 40) -> dict[str, object]:
    """Fetch and decode the CBC bank posted rates change feed (Big5)."""
    response = requests.get(RATE_FEED_URL, timeout=30, verify=False)
    response.raise_for_status()

    text = response.content.decode("big5", errors="replace")
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]

    feed_date = None
    for line in lines:
        match = re.search(r"資料日期：\s*(\d{2,3}/\d{2}/\d{2})", line)
        if match:
            feed_date = match.group(1)
            break

    return {
        "feed_date_roc": feed_date,
        "preview_lines": lines[:max_lines],
        "source_url": RATE_FEED_URL,
    }


def fetch_policy_headlines(limit: int = 10) -> list[dict[str, str]]:
    """Scrape major policy headlines from CBC policy page."""
    soups: list[BeautifulSoup] = []
    for url in (POLICY_NEWS_URL, CBC_HOME_URL):
        try:
            soups.append(BeautifulSoup(_get_html(url), "lxml"))
        except Exception:
            continue

    seen: set[str] = set()
    results: list[dict[str, str]] = []
    for soup in soups:
        links = soup.select('a[href*="/tw/cp-971-"]')
        for a in links:
            href = (a.get("href") or "").strip()
            title = a.get_text(strip=True)
            if not href or not title:
                continue
            full_url = href if href.startswith("http") else f"https://www.cbc.gov.tw{href}"
            if full_url in seen:
                continue
            seen.add(full_url)
            results.append({"title": title, "url": full_url})
            if len(results) >= limit:
                return results

    return results


def build_mvp_snapshot(max_pages: int = 5) -> dict[str, object]:
    fx_df = fetch_fx_rates(max_pages=max_pages)
    rate_feed = fetch_rate_feed_preview()
    policy_headlines = fetch_policy_headlines(limit=10)

    summary = {
        "records": int(len(fx_df)),
        "start_date": None,
        "end_date": None,
        "latest_ntd_usd": None,
        "ma_7": None,
        "change_5d": None,
    }

    if not fx_df.empty:
        summary["start_date"] = str(fx_df["date"].iloc[0])
        summary["end_date"] = str(fx_df["date"].iloc[-1])
        summary["latest_ntd_usd"] = float(fx_df["ntd_usd"].iloc[-1])
        summary["ma_7"] = float(fx_df["ntd_usd"].tail(7).mean())
        if len(fx_df) >= 6:
            summary["change_5d"] = float(fx_df["ntd_usd"].iloc[-1] - fx_df["ntd_usd"].iloc[-6])

    return {
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "summary": summary,
        "sources": {
            "fx": FX_FIRST_PAGE_URL,
            "rate_feed": RATE_FEED_URL,
            "policy_news": POLICY_NEWS_URL,
        },
        "rate_feed": rate_feed,
        "policy_headlines": policy_headlines,
        "fx_rates": fx_df.to_dict(orient="records"),
    }


def save_snapshot(output_dir: str = "data", max_pages: int = 5) -> dict[str, Path]:
    payload = build_mvp_snapshot(max_pages=max_pages)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    fx_df = pd.DataFrame(payload["fx_rates"])
    fx_csv_path = output_path / "cbc_fx_rates.csv"
    fx_df.to_csv(fx_csv_path, index=False)

    snapshot_path = output_path / "cbc_mvp_snapshot.json"
    snapshot_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"fx_csv": fx_csv_path, "snapshot_json": snapshot_path}


if __name__ == "__main__":
    paths = save_snapshot(output_dir="data", max_pages=5)
    print("Saved:")
    for key, value in paths.items():
        print(f"- {key}: {value}")
