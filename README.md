# DocsChat - RAG Document Assistant
Assesment Application Name: Chat with your document Bot
The document Q&A application using RAG. Upload documents, ask questions, get answers backed from the uploaded document content.

## Implementation Note

Built without LangChain or similar frameworks - all RAG components implemented from scratch using direct API calls to demonstrate understanding of core concepts:
- Custom document chunking logic
- Direct integration with Sentence Transformers for embeddings
- Manual vector similarity search with pgvector
- Direct LLM API calls (OpenAI, Ollama)
- Custom streaming response handling

## Assumptions

- Users can upload `.pdf`, `.docx`, and `.txt` files
- AI responses are generated using only uploaded documents
- English language only
- No authentication or user management required

## Features

- Switch between Ollama (qwen2.5:7b) and OpenAI (gpt-4o-mini) models
- Upload/delete documents (PDF, DOCX, TXT)
- Ask questions about uploaded documents
- Clear chat history
- Light/dark theme toggle
- Source citations for AI responses

## Tech Stack

**Backend:**
- FastAPI
- PostgreSQL + pgvector
- Sentence Transformers (embeddings)
- SQLAlchemy

**Frontend:**
- Vanilla JavaScript
- Server-Sent Events (SSE streaming responses)

**AI:**
- Ollama (local LLM)
- OpenAI API (optional)

## Setup

**Prerequisites:**
- Docker & Docker Compose
- 8GB RAM (for Ollama)
- OpenAI API key 

**Install:**

```bash
# Clone repo
git clone https://github.com/ajujohn2009/agoda-ai-doc-bot-assessment.git
cd agoda-ai-doc-bot-assessment

# Create .env file
cp .env.example .env

# Edit .env and add your OpenAI API key
nano .env
```

**.env configuration:**
```bash
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=ragdb
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_MODEL=gpt-4o-mini
```

**Start services:**
```bash
docker-compose build
docker-compose up
```

**Access:**
- UI: http://localhost:8000
- API docs: http://localhost:8000/docs

> **Note:** First startup takes 10-15 minutes while Ollama downloads the model (~2.8GB)

## Usage

1. Go to **Documents** tab
2. Upload your files
3. Switch to **Chat** tab
4. Ask questions
5. View answers with source citations



## Development

**View logs:**
```bash
docker-compose logs -f api
```

**Access database:**
```bash
docker-compose exec db psql -U postgres -d ragdb
```

## How It Works

1. Documents split into chunks (~1200 chars, 150 char overlap)
2. Each chunk converted to 384-dimensional vector
3. Vectors stored in PostgreSQL with pgvector
4. User question embedded and similar chunks retrieved
5. LLM generates answer using retrieved chunks
6. Response streamed back in real-time
