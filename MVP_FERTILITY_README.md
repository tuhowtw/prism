# East Asia Fertility Policy Simulator MVP

## What this MVP includes
- Live data scraping:
  - Taiwan: RIS Table 11 yearly fertility metrics
  - Japan and Korea: World Bank TFR API
- Data outputs:
  - `data/fertility_taiwan_table11_yearly.csv`
  - `data/fertility_east_asia_panel.csv`
  - `data/fertility_rag_docs.json`
  - `data/fertility_mvp_snapshot.json`
- Streamlit demo app:
  - Data trend view
  - Policy intensity simulator
  - RAG + LLM prompt construction demo

## Run steps (PowerShell)
1. Scrape and build snapshot:

```powershell
c:/Users/drunk/howtu_program/econ_policy/.venv/Scripts/python.exe mvp_fertility_simulator.py
```

2. Launch fertility dashboard:

```powershell
c:/Users/drunk/howtu_program/econ_policy/.venv/Scripts/python.exe -m streamlit run app_fertility.py
```

## How LLM/RAG is applied in this demo
1. Retrieval step:
- The app retrieves top policy/statistics snippets from `fertility_rag_docs.json` based on query keyword overlap.

2. Grounded prompt building:
- The app creates an LLM prompt that includes:
  - Latest fertility data by country
  - Retrieved context snippets and source URLs
  - Required answer format (diagnosis, policy package, risks, next data)

3. Response step:
- A heuristic response is shown as a stand-in for real model output.
- In production, this prompt should be sent to an actual LLM API.
