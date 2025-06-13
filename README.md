# UAV Log Viewer

![log seeking](preview.gif "Logo Title Text 1")

This is a JavaScript-based log viewer for MAVLink telemetry and DataFlash logs.  
[Live demo here](http://plot.ardupilot.org).

---

## 🚀 Features

- Visualize UAV flight logs interactively
- Supports both `.bin` (DataFlash) and `.tlog` (MAVLink) formats
- 3D flight path rendering via Cesium
- Realtime graph overlays for telemetry parameters

---

## 🔧 Build Setup

```bash
# install dependencies
npm install

# serve with hot reload at localhost:8080
npm run dev

# build for production with minification
npm run build

# run unit tests
npm run unit

# run e2e tests
npm run e2e

# run all tests
npm test
```

---

## 🐳 Docker

Run the prebuilt Docker image:

```bash
docker run -p 8080:8080 -d ghcr.io/ardupilot/uavlogviewer:latest
```

Or build it locally:

```bash
# Build Docker image
docker build -t <your-username>/uavlogviewer .

# Run Docker image
docker run -e VUE_APP_CESIUM_TOKEN=<your-cesium-ion-token> -it -p 8080:8080 -v ${PWD}:/usr/src/app <your-username>/uavlogviewer

# Visit http://localhost:8080
```

---

## 💬 New Backend Module: `Chatbotbackend/`

This fork introduces a powerful backend module that enables **LLM-driven UAV log analysis**.

### 📁 Directory Structure

```
Chatbotbackend/
├── app/
│   ├── __init__.py                 # Initializes FastAPI app
│   ├── main.py                     # Routing entry point
│   ├── models.py                   # Pydantic data models
│   └── Services/
│       ├── __init__.py
│       ├── mavlink_parser.py       # Parses MAVLink .bin logs to structured JSON
│       └── llm_service.py          # LangChain tools + agent logic
├── uploads/                        # Temporary store for logs
├── .env                            # Contains API keys and config
└── requirements.txt                # Python backend dependencies
```

---

### 🧠 Capabilities

- 📦 Parses `.bin` files (from frontend) into structured telemetry JSON
- 🧠 LLM-powered Q&A with LangChain tools
- 🧰 Built-in tools: GPS loss, RC signal drop, EKF errors, anomaly detection
- 🔌 Gemini/OpenAI-compatible agent backend

---

### ⚙️ Setup

#### 1. Clone and navigate

```bash
git clone https://github.com/<your-username>/UAVLogViewer.git
cd UAVLogViewer/Chatbotbackend
```

#### 2. Create `.env` file

```ini
GOOGLE_API_KEY=your_gemini_api_key
```

#### 3. Install backend dependencies

```bash
pip install -r requirements.txt
```

#### 4. Run the backend

```bash
uvicorn app.main:app --reload
```

The server runs at `http://localhost:8000`.

---

### 🔍 Example LLM-Powered Tools

- `get_highest_altitude`
- `find_first_gps_loss`
- `list_critical_errors`
- `check_rc_signal_loss`
- `summarize_all_anomalies`
- `analyze_raw_telemetry`
- `lookup_ardupilot_documentation`

These tools allow for professional-grade root-cause analysis of flight anomalies, GPS dropouts, and telemetry corruption.

---

### 📦 Backend Dependencies

```txt
fastapi
uvicorn
pydantic
langchain
google-generativeai
pandas
```

---

This extension makes UAVLogViewer not just a telemetry browser, but a **flight analysis assistant** for robotics engineers, researchers, and QA teams.
