# Chat with Database (SQL + LLM)

> Ask questions about your data in natural language. AI generates SQL, runs it, and shows results with charts.

## 🔥 Features

- **Natural Language → SQL** — Ask in plain English, get SQL queries
- **Upload Your Data** — CSV or SQL files, auto-creates queryable database
- **Smart Schema Filtering (RAG)** — Only relevant tables sent to LLM
- **Single LLM Call** — Efficient: SQL + explanation in one API call
- **Auto Correction** — Failed queries retry automatically (up to 3x)
- **Rule-Based Charts** — Bar, line, pie, scatter — no LLM needed
- **100% Free** — Uses Groq (free tier) or Ollama (local)
- **Secure** — 5-layer SQL validation, read-only database connections

## 🏗️ Architecture

```
Frontend (React + Vite)  →  Backend (FastAPI)  →  SQLite (per-user)
                                    ↕
                            Groq API / Ollama (LLM)
                            sentence-transformers (RAG)
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Free Groq API key from [console.groq.com](https://console.groq.com)

### 1. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Configure (add your free Groq API key)
# Edit .env file and replace gsk_your_key_here with your key

# Start server
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

### 3. Open the app

Go to **http://localhost:5173** — upload a CSV/SQL file and start chatting!

## 📁 Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Settings
│   │   ├── models.py            # Pydantic models
│   │   ├── routers/             # API endpoints
│   │   │   ├── upload.py        # File upload
│   │   │   ├── chat.py          # Chat/query
│   │   │   └── schema.py        # Schema exploration
│   │   ├── services/            # Business logic
│   │   │   ├── file_processor   # CSV/SQL → SQLite
│   │   │   ├── schema_extractor # DB schema extraction
│   │   │   ├── rag_filter       # RAG schema filtering
│   │   │   ├── llm_service      # Groq/Ollama integration
│   │   │   ├── sql_validator    # 5-layer SQL safety
│   │   │   ├── query_executor   # Execution + retry loop
│   │   │   └── chart_service    # Rule-based charts
│   │   └── utils/database.py    # SQLite connection manager
│   └── data/                    # Per-user databases
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Main layout
│   │   ├── components/          # React components
│   │   └── api/client.js        # API client
│   └── index.html
└── README.md
```

## ⚙️ LLM Options (Both Free)

| Provider | Speed | Setup |
|----------|-------|-------|
| **Groq** | ⚡ Very fast | Get free key → add to .env |
| **Ollama** | 🐢 Depends on hardware | Install Ollama → `ollama pull llama3.2` |

System auto-detects which is available. Groq is tried first.

## 🔒 Security

- 5-layer SQL validation (regex → injection → multi-statement → AST → whitelist)
- Read-only database connections (URI mode=ro + PRAGMA query_only)
- Per-user isolated SQLite databases
- Query timeout (5 seconds)
- Result row limit (1000 rows)
