# UAV Log Viewer & AI Flight-Assistant

<p align="center">
  <img src="preview.gif" alt="UAV Log Viewer demo" width="650"/>
</p>

A modern web application for analysing and visualising UAV flight logs **with an integrated LLM-powered chat assistant**.  
Upload a `tlog` or `.bin`, explore plots, and ask natural-language questions such as *“What was the max climb rate?”* or *“Do you see any GPS anomalies?”* — the assistant replies instantly and proposes follow-up questions.

---

## ✨ Features
* 📈 Interactive plots for attitude, GPS, battery, RC and custom messages  
* 🔍 Semantic search over every telemetry field (Cohere embeddings)  
* 🤖 Chat assistant (Groq Llama-3) that:
  * Computes on-the-fly metrics (duration, distance, altitude, …)  
  * Detects anomalies via reasoning (wind, satellite drop-outs, attitude spikes)  
  * Suggests **answerable** follow-up questions
* 🏗 FastAPI backend, Vue 2 frontend (Webpack)  
* 🐳 Single-command Docker build  
* ⚡ GitHub Actions CI + rsync deploy workflow

---

## 🖼️ Project Structure

```bash
UAVLogViewer
├─ backend                     # (ADDED)
│  ├─ run.py                   # local entry-point: uvicorn
│  ├─ requirements.txt         # Python deps
│  ├─ setup.py                 # pip-installable package
│  └─ uav_log_viewer           # Python package
│     ├─ __init__.py
│     ├─ core.py               # FastAPI factory
│     ├─ analysis              # telemetry analytics
│     │  ├─ __init__.py
│     │  ├─ data_extractor.py
│     │  ├─ telemetry.py
│     │  └─ anomalies.py
│     ├─ chat                  # LLM assistant
│     │  ├─ __init__.py
│     │  ├─ prompt.py
│     │  ├─ processor.py
│     │  └─ conversation.py
│     └─ routes                # FastAPI routers
│        ├─ __init__.py
│        ├─ chat.py
│        └─ analysis.py
│
├─ src                         # Vue 2 front-end
│  ├─ components
│  │  └─ widgets
│  │     └─ ChatWidget.vue     # (ADDED)
│  └─ …                        # views, router, store
│
├─ build/                      # webpack configs
├─ config/                     # extra webpack / jest config
├─ static/                     # assets copied verbatim
│
├─ .github
│  └─ workflows
│     ├─ nodejs.yml            # build / test
│     ├─ nodejsdeploy.yml      # rsync deploy
│     ├─ nodejsdeploystable.yml
│     └─ release.yml           # docker release
│
├─ Dockerfile
├─ package.json
├─ README.md
└─ preview.gif                 # animated demo

---

```


## 🚀 Quick Start

### 1. Clone & install

```bash
git clone https://github.com/rcaii/UAVLogViewer.git
cd UAVLogViewer

# ─────────────  Front-end  ─────────────
npm install                        # needs Node ≥ 18

# ─────────────  Back-end  ─────────────
python3 -m venv backend/venv
source backend/venv/bin/activate
pip install -r backend/requirements.txt
```

### 2. Environment variables

Create `backend/.env` and add your keys:

| Variable             | Description                                   |
|----------------------|-----------------------------------------------|
| `GROQ_API_KEY`       | API key for Groq Llama-3 (chat & anomalies)    |
| `COHERE_API_KEY`     | API key for Cohere embeddings / rerank        |
| `GROQ_API_BASE`      | _(opt)_ Custom Groq endpoint                  |
| `GROQ_DEFAULT_MODEL` | _(opt)_ Model name (defaults to llama3-70b-8192) |

**Never commit keys – store them as GitHub Secrets for CI.**

### 3. Run locally

```bash
# terminal ① – FastAPI back-end
cd backend
python run.py          # http://localhost:8000 (docs at /docs)

# terminal ② – Vue front-end
npm run dev            # http://localhost:8080
```

The frontend proxies API calls to `localhost:8000` via CORS (already enabled).

### 4. Production build

```bash
npm run build          # outputs static files to dist/
```

Serve the `dist` folder behind Nginx, or build the Docker image:

```bash
docker build -t uavlogviewer .
docker run -p 8080:8080 -p 8000:8000 uavlogviewer
```

---

## ⚙️ Back-end endpoints

| Method | Path      | Description                      |
|--------|-----------|----------------------------------|
| GET    | `/health` | Health check (“ok”)              |
| POST   | `/chat/`  | JSON `{question, telemetry?}` → `{answer, suggested_questions}` |
| POST   | `/analysis/metrics` | _(example)_ compute full metric set |

Interactive docs available at `http://localhost:8000/docs` (Swagger UI).

---

## 🧪 Testing

```bash
# Vue unit & e2e
npm run unit          # or npm test

# Python type check & lint (optional)
mypy backend/uav_log_viewer
pytest                # once you add test_*.py
```

---

## 🤖 CI / CD

* **build.yml** – Node build + unit tests  
* **nodejsdeploy.yml** – rsync deploy (needs `DEPLOY_KEY`, `SERVER_IP`, `USERNAME`, `SERVER_DESTINATION` and `SERVER_PORT` GitHub Secrets)  
* **release.yml** – Docker build & push (optional)



```mermaid
flowchart LR

    %% Front-end chat UI: collects question, shows reply + chips
    A[ChatWidget<br/>(Vue 3)] 

    %% REST entry point: validates JSON, hands to orchestrator
    B(FastAPI<br/>/chat)

    A -- ".tlog JSON → POST" --> B

    %% Orchestrator: decides anomaly / metric / general path
    P[processor.py<br/>orchestrator] 
    B --> P

    %%  anomaly branch – semantic slice → LLM
    P -- anomaly? --> AN[anomaly pipeline]
    %%  metric branch – slice + full-log metrics → LLM
    P -- metric?  --> MT[metric pipeline]
    %%  general fallback – no telem / non-UAV question
    P -- general  --> GE[general prompt]
    
    %% ───── anomaly sub-flow ─────
    %%   semantic field selection
    DE1[data_extractor.py] 
    %%   build threshold-aware prompt
    PR1[_build_prompt()] 
    AN --> DE1 --> PR1

    %% ───── metric sub-flow ─────
    DE2[data_extractor.py]
    TM[telemetry.py<br/>compute_metrics]
    MT --> DE2
    MT --> TM
    PR2[metric prompt builder]
    DE2 --> PR2
    TM  --> PR2

    %%  common LLM endpoint
    LLM[Groq Llama-3]
    PR1 --> LLM
    PR2 --> LLM
    GE  --> LLM
    LLM --> P

    %% conversation history buffer
    CS[(conversation_state<br/>last 15 turns)]
    P --> CS

    P --> B
    B -- "JSON {answer, suggested}" --> A
    A -- "chip click" --> B

