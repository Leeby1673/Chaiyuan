# 財猿 (Chaiyuan)

台灣股市 Line Bot，透過 Gemini Function Calling 讓使用者用自然語言查詢股票資訊。

## 功能

- 透過 Line 傳送任意文字訊息與 Bot 互動
- Gemini 自動判斷意圖，決定是否查詢股票資料
- 串接 TWSE OpenAPI 取得台股當日收盤資訊
- 以繁體中文回覆分析結果

## 技術架構

```
使用者 Line 訊息
    → FastAPI Webhook（linebot v3 驗簽）
    → Gemini Function Calling（判斷意圖）
        ├── get_stock_data(stock_code)
        │       → TWSE OpenAPI
        │       → 結果回饋 Gemini → 自然語言回覆
        └── 一般對話 → 直接回覆
```

**主要套件**

| 用途 | 套件 |
|---|---|
| Web framework | FastAPI + Uvicorn |
| Line Bot | line-bot-sdk v3 |
| LLM | google-genai (Gemini 2.0 Flash) |
| HTTP client | httpx |
| 股票資料 | TWSE OpenAPI（免費，無需 key） |

## 專案結構

```
app/
├── main.py                  # FastAPI app factory
├── config.py                # 環境變數設定
├── webhook/
│   └── router.py            # POST /webhook
├── handlers/
│   └── message_handler.py   # Gemini function call 流程
└── services/
    ├── gemini_service.py     # Gemini client + tool 定義
    └── twse_service.py       # TWSE OpenAPI client

tests/                       # 對應 app/ 結構，全 mock
```

## 快速開始

### 1. 安裝依賴

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt -r requirements-dev.txt
```

### 2. 設定環境變數

```bash
copy .env.example .env
```

編輯 `.env` 填入：

```
LINE_CHANNEL_SECRET=        # Line Developer Console 取得
LINE_CHANNEL_ACCESS_TOKEN=  # Line Developer Console 取得
GEMINI_API_KEY=             # Google AI Studio 取得
```

### 3. 啟動伺服器

```bash
uvicorn app.main:app --reload --port 8000
```

### 4. 暴露給 Line Webhook（開發用）

```bash
ngrok http 8000
```

將 ngrok 提供的 `https://xxxx.ngrok-free.app/webhook` 填入 Line Developer Console 的 Webhook URL。

## 測試

```bash
pytest
pytest -v                              # 詳細輸出
pytest tests/services/ -v              # 單一目錄
```

目前 27 個測試，全 mock，不需要真實 API key。

## 環境需求

- Python 3.13+
- Line Developer 帳號（免費）
- Google AI Studio API key（免費額度）
