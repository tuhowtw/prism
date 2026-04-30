from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from mvp_cbc_watcher import save_snapshot


st.set_page_config(page_title="Taiwan Central Bank Watcher MVP", layout="wide")


def load_snapshot(snapshot_path: Path) -> dict:
    return json.loads(snapshot_path.read_text(encoding="utf-8"))


st.title("Taiwan Central Bank Watcher MVP")
st.caption("Scraped from CBC public pages for demo use")

left, right = st.columns([1, 3])
with left:
    pages = st.slider("FX pages to scrape", min_value=1, max_value=20, value=5)
    refresh = st.button("Refresh Data", type="primary")

if refresh:
    with st.spinner("Scraping CBC pages and generating snapshot..."):
        paths = save_snapshot(output_dir="data", max_pages=pages)
else:
    data_dir = Path("data")
    snapshot_default = data_dir / "cbc_mvp_snapshot.json"
    if not snapshot_default.exists():
        with st.spinner("No cached data found. Running first scrape..."):
            paths = save_snapshot(output_dir="data", max_pages=pages)
    else:
        paths = {"snapshot_json": snapshot_default, "fx_csv": data_dir / "cbc_fx_rates.csv"}

payload = load_snapshot(Path(paths["snapshot_json"]))
fx_df = pd.DataFrame(payload.get("fx_rates", []))
summary = payload.get("summary", {})

metric_1, metric_2, metric_3, metric_4 = st.columns(4)
metric_1.metric("Latest NTD/USD", f"{summary.get('latest_ntd_usd')}")
metric_2.metric("7-day avg", f"{summary.get('ma_7')}")
metric_3.metric("5-day change", f"{summary.get('change_5d')}")
metric_4.metric("Records", f"{summary.get('records')}")

if not fx_df.empty:
    fx_df["date"] = pd.to_datetime(fx_df["date"])
    fig = px.line(
        fx_df,
        x="date",
        y="ntd_usd",
        title="NTD/USD Interbank Close Rate",
        markers=True,
    )
    fig.update_layout(height=430)
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Policy Headlines (CBC Major Policy)")
policy_items = payload.get("policy_headlines", [])
if policy_items:
    for item in policy_items:
        st.markdown(f"- [{item['title']}]({item['url']})")
else:
    st.info("No policy headlines parsed in this run.")

st.subheader("Bank Rate Feed Preview")
rate_feed = payload.get("rate_feed", {})
st.write("Feed date (ROC):", rate_feed.get("feed_date_roc"))
preview_lines = rate_feed.get("preview_lines", [])
if preview_lines:
    st.code("\n".join(preview_lines[:25]), language="text")

with st.expander("Data source links"):
    sources = payload.get("sources", {})
    for name, url in sources.items():
        st.markdown(f"- **{name}**: {url}")

st.caption("Note: This MVP disables TLS certificate verification for cbc.gov.tw in this environment due certificate-chain issues.")
