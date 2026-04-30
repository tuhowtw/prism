# Taiwan Central Bank Watcher MVP Demo

## What this demo does
- Scrapes NTD/USD interbank close rates from CBC pages.
- Pulls the CBC bank posted rate change feed (`bkrldc.txt`).
- Pulls major policy headlines from CBC major policy page.
- Saves outputs to:
  - `data/cbc_fx_rates.csv`
  - `data/cbc_mvp_snapshot.json`
- Shows a Streamlit dashboard with metrics, trend chart, and feed preview.

## Run steps (PowerShell)
1. Generate snapshot files only:

```powershell
c:/Users/drunk/howtu_program/econ_policy/.venv/Scripts/python.exe mvp_cbc_watcher.py
```

2. Launch dashboard:

```powershell
c:/Users/drunk/howtu_program/econ_policy/.venv/Scripts/python.exe -m streamlit run app.py
```

## Notes
- This environment currently has TLS validation issues for `cbc.gov.tw`, so the scraper uses unverified HTTPS requests for demo purposes.
- For production, replace this with proper certificate trust configuration.
