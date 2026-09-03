# MUST Academic Advisor — RAG Retrieval API

Retrieval-Augmented Generation (RAG) service for the **MUST (Misr University for Science and Technology)** Academic Advisor AI (Faculty of Computers & Artificial Intelligence — CS, AI, and IS Majors).

The API retrieves and reranks official university regulations, course catalogs, prerequisites, GPA registration rules, and semester plans using a hybrid reranker combining vector similarity, exact course code normalization, GPA boundary rules, semester matching, and department/university elective intent detection.

---

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/abdulr2005/must-rag-api.git
cd must-rag-api

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the root directory (see `.env.example`):

```env
GEMINI_API_KEY=your_gemini_api_key_here
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_service_or_anon_key
```

### 3. Run the Server

```bash
uvicorn rag_api:app --reload --host 127.0.0.1 --port 8000
```

The server will start at `http://127.0.0.1:8000`.
- Health Check: `GET /`
- Search Endpoint: `POST /rag/search`

---

## 🧪 Testing & Validation

The service includes an automated benchmark and regression suite:

### Run the Full Benchmark (Part A Static Checks + Part B Live API Tests)
```bash
python test_rag_absolute.py
```
> **Benchmark Score:** 39/39 Checks Passed (100%)

### Run Static Knowledge Base Checks Only (no server needed)
```bash
python test_rag_absolute.py --static-only
```

### Run Live Retrieval Tests Only
```bash
python test_rag_absolute.py --live-only
```

### Run Regression Test Suite v2
```bash
python test_rag_v2.py
```

---

## 📡 API Specification

### Search Endpoint: `POST /rag/search`

#### Request Body
```json
{
  "question": "الحد الأقصى للساعات لو المعدل التراكمي 3.5",
  "top_k": 3
}
```

#### Response Format
```json
{
  "question": "الحد الأقصى للساعات لو المعدل التراكمي 3.5",
  "count": 3,
  "results": [
    {
      "rank": 1,
      "text": "المادة 1 من قواعد التسجيل: الحد الأدنى للتسجيل في الفصل الدراسي هو 12 ساعة معتمدة ... الحد الأقصى 18 ساعة ويجوز زيادة الحد الأقصى إلى 23 ساعة للطلاب الحاصلين على معدل لا يقل عن 3 ...",
      "score": 1.0914,
      "vector_score": 0.7414,
      "metadata": {
        "chunk_id": "gpa_article_1",
        "doc_type": "gpa_article",
        "article": 1,
        "confidence": "verified"
      }
    }
  ]
}
```

---

## 🤖 Agent Integration

For developers building the conversational AI Agent (connecting the UI to this RAG service):

1. **Tool Binding**: Register a tool in your LLM framework (Google Gemini SDK, LangChain, or custom) calling `POST http://127.0.0.1:8000/rag/search`.
2. **Two-Track Architecture**:
   - **Track A (Catalog & Bylaws)**: Route questions regarding courses, prerequisites, elective pools, and GPA rules to `/rag/search`.
   - **Track B (Student Records)**: For personal queries ("فاضلي كام ساعة للتخرج؟"), do not hallucinate earned hours; prompt the student for their earned hours or query student SIS if available (total requirement: ~140 hours for CS/AI, 141 for IS).

See [`docs/MUST_RAG_System_Design.md`](docs/MUST_RAG_System_Design.md) for full architectural guidelines.

---

## 📂 Project Structure

```text
├── rag_api.py              # FastAPI application & hybrid reranker
├── chunks.json             # 231 clean, normalized knowledge base chunks
├── ingest.py / ingest_v2.py # Supabase embedding & upsert pipeline
├── test_rag_absolute.py    # 39-test static & live benchmark suite
├── test_rag_v2.py          # 8-test regression suite
├── requirements.txt        # Python package dependencies
├── .env.example            # Environment template
└── docs/
    ├── MUST_RAG_System_Design.md
    └── MUST_RAG_Coverage_Validation.md
```
