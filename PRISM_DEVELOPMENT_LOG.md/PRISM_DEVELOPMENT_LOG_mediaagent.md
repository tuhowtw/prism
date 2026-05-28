# Prism: AI Economic Policy & Perception Simulator
## 開發與偵錯日誌 (Development & Debugging Log)

**日期：** 2026-05-26  
**目標：** 修正新舊版本功能整合後的系統阻斷型錯誤（Blockers），成功導入 Google Gemini API 管線，並優化 Streamlit 多執行緒 UI 互動與例外處理。

---

## 📋 執行摘要 (Executive Summary)

本階段工作主要聚焦於將 **Prism 政策感知模擬器** 底層的核心代理（Agent）與模擬管線（Simulation Pipeline）全面對接至 **Google Gemini API**，並全面排查在大規模非同步併發下導致系統卡死、崩潰與存檔失敗的底層架構問題。

經過一系列深度排查，我們成功解決了 **環境依賴、API 驗證、JSON 截斷、多執行緒 UI 狀態不同步、資料序列化崩潰** 等 7 項重大 Bug，目前系統已具備完整跑通「問卷設計 (Agent 1) -> 群體模擬 (Simulation) -> 策略分析 (Agent 2)」全流程的能力。

---

## 🛠️ 重大修復與架構優化清單

### 1. 解決環境依賴與虛擬環境啟動問題
* **現象：** 終端機回報 `zsh: command not found: streamlit` 與 `ModuleNotFoundError: No module named 'litellm'`。
* **原因：** 執行指令時未正確切換至專案根目錄，且未激活內建的虛擬環境 (`.venv`)。
* **修復：** 導引進入虛擬環境，並一鍵補齊專案核心依賴套件：
  ```bash
  source .venv/bin/activate
  pip install streamlit litellm pandas plotly python-dotenv google-generativeai
  ```

### 2. 模型驗證與模型名稱對接 (LiteLLM Layer)
* **現象：** 拋出 `AnthropicException: invalid x-api-key` 以及 `404 NOT_FOUND` 找不到特定模型。
* **原因：** 1. 引擎底層的 `AGENT_MODEL` 預設硬編碼為 Claude 模型，導致填入 Gemini Key 時發生權限錯誤。
  2. 手動輸入的非標準模型名稱無法被 Google API 識別。
* **修復：** 將硬編碼預設值統一調整為 LiteLLM 標準前綴格式（`gemini/`），並全面升級採用最新輕量化模型：
  * **全局預設模型 (Agent & Sim)：** `gemini/gemini-3.1-flash-lite` (兼具極速反應與低成本優勢，極度適合 100+ 併發模擬場景)
  * **嵌入分析模型 (Embedding)：** `gemini/text-embedding-004` (確保 Agent 1 進行語義分析時有正確的模型可用)

### 3. 解除 Token 截斷與 JSON 解析崩潰
* **現象：** `Clarify failed: No JSON object found in response: ...`
* **原因：** Agent 1 在設計問卷時生成的結構化 JSON 文本較為龐大，而原程式碼限制 `max_tokens=1024`，導致回應在字串中間被系統截斷，不完整的 JSON 字串無法被底層解析器識別。
* **修復：** 將 `run_agent1_clarify` 函數中的 `max_tokens` 提升至 `4096`，確保 AI 有足夠的上下文空間將結構化資料完整閉合。

### 4. 修正 Streamlit 多執行緒 UI 進度條卡死 Bug
* **現象：** 進入模擬階段後，進度條始終卡在 `0/108` 毫無反應，但背景仍在執行。
* **原因：** 原版 `page_run()` 的非同步回報機制（`_cb`）將進度寫入了一個孤立的區域變數，而前端前端監聽的是 `responses_holder` 字典，導致網頁 UI 變成「瞎子」。
* **修復：** 重構 `_run_sim()` 回呼函數，讓背景執行緒的進度直接強制寫入 UI 監聽的共用狀態中，並在派發前強制將 API Key 寫入環境變數，防止 Embedding 模組（`gemini/text-embedding-004`）在背景初始化時因拿不到 Key 而靜默崩潰。

### 5. 阻斷型錯誤：解決物件未序列化（Not JSON Serializable）崩潰
* **現象：** 模擬結束或產生問卷時，頻繁跳出 `TypeError: Object of type X is not JSON serializable`，導致進度無法推進。
* **原因：** 系統在關鍵節點會調用 `save_manifest()` 將當前進度打包存成 JSON 檔。然而，Python 內建的 `json` 模組無法直接識別自定義的 Pydantic/DataClass 物件（如 `MediaHeadline` 和 Agent 2 的 `AnalysisOutput`）。
* **修復：** 在 `prism_app.py` 內的 `_build_manifest` 與 `_load_run_into_session` 函數中，手動加入「物件 ⇄ 字典 (Dict)」的雙向轉換邏輯，實現安全的結構化儲存。

### 6. 徹底靜音 LiteLLM 背景多執行緒日誌報錯
* **現象：** 終端機高頻噴出 `Task was destroyed but it is pending!` 及 `RuntimeError: Queue is bound to a different event loop`。
* **原因：** Streamlit 的重新渲染機制會頻繁建立新的執行緒，而 LiteLLM 的遙測與成功日誌 Queue 綁定在舊的 Event Loop 上，引發非同步衝突。
* **修復：** 在 `prism_engine.py` 初始化階段引入「五神裝」徹底關閉遙測與背景回呼，不干擾核心 API 回傳：
  ```python
  os.environ["LITELLM_TELEMETRY"] = "False"
  litellm.success_callback = []
  litellm.failure_callback = []
  litellm.callbacks = []
  litellm.suppress_debug_info = True
  litellm.set_verbose = False
  ```

---

## 📈 現狀分析與下一步優化方針 (429 Rate Limit)

目前在免費版 Gemini API 額度下（限制 **15 RPM / 每分鐘 15 次請求**），當模擬規模達到 108 次呼叫時，系統會撞擊到 429 流量牆。

雖然新版程式內建了指數退避重試（Exponential Backoff），但在非同步 `asyncio.gather` 併發下，容易引發「**驚群效應 (Thundering Herd)**」——即幾十個任務同時失敗、同時睡覺、又同時醒來再次塞爆 API。

### 💡 下一步優化備選策略（已完成理論論證，暫未改動程式碼）：
1. **策略 A (動態節流輸送帶)：** 在非同步派發前，依據 15 RPM 的限制，強制讓每個任務錯開 `(60/15) * 併發數` 秒，從源頭避免 429 觸發。
2. **策略 B (舊版批次精髓復刻)：** 引入舊版的 Chunking 機制，將 108 個任務切為每 10 個一包，每跑完一包強制 `await asyncio.sleep(25)`，讓進度條極具規律地推進。


---
*日誌維護人：開發團隊*
