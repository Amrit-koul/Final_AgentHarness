# AgentHarness — Governed BFSI Agentic AI Platform

AgentHarness is a governed, demo-grade BFSI agentic AI platform. It showcases how a financial institution can build, register, monitor, and govern multiple AI agents through a centralized governance and observability control plane.

The demo includes three primary use cases:
1. **Policy Assistant**: Interactive chat agent checking bank policies.
2. **Loan Assessment**: RAG-based agent evaluating retail loan eligibility.
3. **Collections Intelligence**: A multi-step workflow simulating account risk profiling, trust gating, and next-best-action recommendations.

---

## Technical Stack & Architecture

- **Backend**: FastAPI app (`banking_agents.main`) orchestrating agent execution, pre/post-run policy checks, guardrails, and audit logging.
- **Frontend**: React/Vite UI connecting to the Backend's control plane and agent runtime.
- **Framework**: `agent_harness` — a generic, reusable governance library for schemas, kill-switches, and degradation monitoring.

---

## Local Setup & Quickstart

### Prerequisites
- **Python 3.10+**
- **Node.js 18+**
- **Groq API Key** (required for LLM operations)
- **LangSmith API Key** (optional, for tracing)

---

### 1. Backend Setup

1. **Navigate to the Backend directory:**
   ```bash
   cd Backend
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv .venv
   # On Windows:
   .\.venv\Scripts\activate
   # On macOS/Linux:
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set environment variables:**
   Configure a `.env` file in `Backend/banking_agents/.env` or export them directly:
   ```bash
   # Required for LLM execution:
   GROQ_API_KEY="your_groq_api_key_here"

   # Optional for LangSmith tracing:
   LANGCHAIN_TRACING_V2="true"
   LANGCHAIN_API_KEY="your_langsmith_api_key_here"
   LANGCHAIN_PROJECT="aria-agent-harness-demo"
   ```

5. **Ingest policy documents:**
   Run the document ingestion script to populate the local vector store:
   ```bash
   python data_ingestion/ingest_docs.py
   ```

6. **Start the FastAPI server:**
   ```bash
   python -m uvicorn banking_agents.main:app --host 127.0.0.1 --port 8000
   ```

---

### 2. Frontend Setup

1. **Navigate to the Frontend directory:**
   ```bash
   cd ../Frontend
   ```

2. **Install package dependencies:**
   ```bash
   npm install
   ```

3. **Configure environment variable:**
   Verify or set the API base url in your shell (default is `http://127.0.0.1:8000`):
   ```bash
   VITE_API_BASE="http://127.0.0.1:8000"
   ```

4. **Start the development server:**
   ```bash
   npm run dev
   ```

5. Open the web browser at **`http://localhost:5173`** to access the dashboard.

---

## Verification & Smoke Checks

With the backend server running, you can run the following PowerShell/Bash commands to verify key services:

- **Health check:**
  ```bash
  curl http://127.0.0.1:8000/health
  ```
- **List registered agents:**
  ```bash
  curl http://127.0.0.1:8000/api/v1/control/agents
  ```
- **Trigger collections workflow run:**
  ```bash
  curl -X POST -H "Content-Type: application/json" -d '{"account_id":"ACC-DEMO-01"}' http://127.0.0.1:8000/api/v1/control/demo/run-collections
  ```
- **Run Backend Tests:**
  ```bash
  cd Backend
  python -m unittest discover -s tests -v
  ```
