# AI Study Notes RAG Assistant

This repository is a learning-focused Retrieval-Augmented Generation project built around study notes. The backend already contains the main RAG pipeline, user authentication, chat sessions, evaluation utilities, and ChromaDB storage. The frontend exists as a Vite + React workspace and is still at scaffold stage.

## What the project currently does

- Ingests `.txt` study notes from the `knowledge/` directory or from manual API input
- Splits note content with a semantic chunking pipeline
- Generates embeddings with either Gemini or OpenAI
- Stores chunks in ChromaDB with duplicate protection
- Retrieves context with vector search, optional hybrid keyword scoring, and optional reranking
- Detects comparison questions and tries to balance final context across both topics
- Answers questions directly through the RAG API
- Supports authenticated chat sessions with SSE token streaming
- Evaluates retrieval and answer quality against JSON test cases

## Repository structure

```text
RAG_projects/
|-- backend/      Django + DRF API, RAG pipeline, Chroma persistence
|-- frontend/     Vite + React app scaffold
|-- knowledge/    Topic-based source notes used for ingestion
`-- README.md
```

Key backend areas:

- `backend/rag/services/` contains ingestion, retrieval, reranking, generation, evaluation, and provider integrations.
- `backend/chat/` contains session/message APIs and SSE streaming responses.
- `backend/users/` contains registration, login, and JWT-based auth flow.
- `backend/chroma_db/` is the local persisted vector store.

## Backend architecture

The backend is a Django 6 + Django REST Framework application with three main domains:

- `users`: custom user model, registration, login, JWT auth
- `chat`: chat sessions, stored messages, streaming assistant responses
- `rag`: note ingestion, retrieval, answer generation, evaluation, maintenance endpoints

Retrieval flow at a high level:

1. Generate an embedding for the user question.
2. Query Chroma for candidate chunks.
3. Optionally diversify or expand retrieval for comparison questions.
4. Optionally apply hybrid scoring with vector similarity plus BM25-style keyword matching.
5. Optionally rerank candidates with the configured LLM.
6. Select final chunks and generate a grounded answer from retrieved context.

## Tech stack

Backend:

- Python
- Django 6
- Django REST Framework
- ChromaDB
- `google-genai`
- `openai`
- `rank-bm25`
- SQLite by default, MySQL optional via environment variables

Frontend:

- React 19
- Vite
- ESLint

## Setup

### 1. Backend

From the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

The backend will run at `http://127.0.0.1:8000/`.

### 2. Frontend

From the repository root:

```powershell
cd frontend
npm install
npm run dev
```

The frontend is currently the default Vite starter and is not yet wired to the backend APIs.

## Environment variables

Create `backend/.env` and define the values you need.

Core app settings:

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG=true`
- `DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost`
- `CORS_ALLOW_ALL_ORIGINS=true`
- `JWT_ACCESS_TOKEN_LIFETIME_SECONDS=604800`

Database:

- SQLite is the default with no extra configuration.
- Set `MYSQL_DATABASE` to switch to MySQL.
- Optional MySQL variables: `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST`, `MYSQL_PORT`

RAG and storage:

- `LLM_PROVIDER=gemini` or `LLM_PROVIDER=openai`
- `KNOWLEDGE_BASE_DIR=../knowledge`
- `CHROMA_PERSIST_DIR=./chroma_db`
- `CHROMA_COLLECTION_NAME=study_notes`
- `RAG_TOP_K=3`
- `RAG_RETRIEVE_K=8`
- `RAG_FINAL_TOP_N=3`
- `RAG_ENABLE_RERANKING=true`
- `RAG_ENABLE_HYBRID_SEARCH=true`
- `RAG_HYBRID_VECTOR_WEIGHT=0.7`
- `RAG_HYBRID_KEYWORD_WEIGHT=0.3`
- `RAG_HYBRID_CANDIDATE_K=8`
- `CHAT_MAX_HISTORY_PAIRS=3`
- `RAG_CHAT_MAX_RETRIEVED_CHUNKS=4`
- `LLM_MAX_OUTPUT_TOKENS=512`

Gemini provider:

- `GEMINI_API_KEY`
- `GEMINI_MODEL=gemini-2.0-flash`
- `GEMINI_EMBEDDING_MODEL=text-embedding-004`

OpenAI provider:

- `OPENAI_API_KEY`
- `OPENAI_MODEL=gpt-4.1-mini`
- `OPENAI_EMBEDDING_MODEL=text-embedding-3-small`

## Knowledge base format

The directory-based ingestion flow expects `.txt` files under `knowledge/`. Topic names are inferred from the first folder under the base path.

Example:

```text
knowledge/
|-- genai/ai.txt
|-- machine_learning/ml.txt
|-- deep_learning/dl.txt
|-- devops/devops.txt
`-- software_engineering/se.txt
```

## API overview

Base URL: `http://127.0.0.1:8000`

Public/auth endpoints:

- `POST /auth/register`
- `POST /auth/login`

RAG endpoints:

- `GET /health`
- `POST /notes/ingest`
- `POST /ask`
- `GET /evaluate`
- `POST /evaluate`
- `POST /maintenance/chroma/cleanup-duplicates`

Chat endpoints:

- `POST /chat/start-session`
- `GET /chat/sessions`
- `GET /chat/messages/<session_id>`
- `POST /chat/send-message`
- `DELETE /chat/session/<session_id>`

Authenticated endpoints expect:

```text
Authorization: Bearer <access_token>
```

## Example requests

Register:

```http
POST /auth/register
Content-Type: application/json

{
  "username": "student1",
  "email": "student1@example.com",
  "password": "StrongPass123"
}
```

Ingest the full `knowledge/` directory:

```http
POST /notes/ingest
Content-Type: application/json

{
  "ingest_from_knowledge_dir": true
}
```

Ingest a single note manually:

```http
POST /notes/ingest
Content-Type: application/json

{
  "title": "Transformer Basics",
  "topic": "genai",
  "source": "manual_note",
  "content": "Transformers rely on self-attention to model relationships between tokens..."
}
```

Ask a question:

```http
POST /ask?top_k=3
Content-Type: application/json

{
  "question": "What is the difference between machine learning and deep learning?"
}
```

Run evaluation:

```http
GET /evaluate
```

Or with an explicit file:

```http
POST /evaluate
Content-Type: application/json

{
  "file_path": "rag/evaluation/test_questions.json"
}
```

## Evaluation

The default evaluation file lives at:

`backend/rag/evaluation/test_questions.json`

Each case contains:

- `question`
- `expected_topic`
- `expected_keywords`

The evaluation service reports retrieval placement, keyword matches, reranking behavior, and average scores across all test cases.

## Current project status

- The backend is the primary working part of the project.
- The retrieval stack already includes semantic chunking, hybrid search, reranking, and comparison-aware selection.
- Chat is implemented on the backend and streams responses with server-sent events.
- The frontend is still a starter template and needs integration with auth, ingestion, question answering, and chat APIs.

## Notes

- Chroma collections are provider-aware, so changing `LLM_PROVIDER` or embedding models changes the active collection name.
- Duplicate chunks are skipped using stable chunk IDs derived from source, index, and normalized chunk text.
- If no context is found, the answer layer falls back to: `No sufficient information found in knowledge base.`
