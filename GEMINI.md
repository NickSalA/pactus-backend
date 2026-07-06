# AGENTS.md - ContractAI Backend

## Commands

### Testing
```bash
uv run pytest                                    # All tests
uv run pytest tests/chatbot/...                 # Single module
uv run pytest tests/chatbot/infrastructure/agent/test_graph.py::test_name  # Single test
```

### Lint & Typecheck
```bash
uv run ruff check src/                          # Lint
uv run ty check src/                            # Typecheck (ty is strict)
```

### Run
```bash
uv run fastapi dev src/pactus_backend/main.py
uv run contractai-backend                      # Uses pyproject entry point
```

## Architecture

- **Framework**: FastAPI + SQLModel + PostgreSQL
- **Chatbot**: Multi-agent LangGraph (A1 Context → A2 Permissions → A3 Conversation)
- **Vector search**: Qdrant + LlamaIndex
- **LLM**: Google Gemini via LangChain (`ChatGoogleGenerativeAI`)
- **Package manager**: uv (not pip)

## Module Structure

```
src/pactus_backend/
├── modules/
│   ├── chatbot/        # LangGraph multi-agent chatbot
│   │   ├── api/        # Routers, schemas, dependencies
│   │   ├── application/  # Services, repository interfaces
│   │   ├── domain/     # Entities, exceptions
│   │   └── infrastructure/  # Agent impl, repos
│   ├── documents/      # Document management
│   ├── templates/     # Contract templates
│   └── ...            # Other modules
├── core/              # Shared exceptions, base classes
├── shared/            # Config, middlewares, infrastructure
└── factory.py         # FastAPI app creation
```

## Chatbot Key Files

- `modules/chatbot/infrastructure/agent/graph.py` - LangGraph workflow definition
- `modules/chatbot/infrastructure/agent/adapter.py` - LLM adapter (invokes graph)
- `modules/chatbot/application/services/chatbot_service.py` - Main service
- `modules/chatbot/api/routers/chat_router.py` - API endpoints

## Important Patterns

1. **Service Dependency Injection**: Services are injected via FastAPI `Depends()` in routers
2. **Repository Pattern**: Abstract interfaces in `application/repositories/`, implementations in `infrastructure/`
3. **LangGraph State**: Agent state defined in `infrastructure/agent/state.py`
4. **Checkpointer**: PostgreSQL checkpointer for LangGraph conversation memory

## Known Quirks

- `ConversationTable.content` stores messages as JSONB, not as relationship
- Token usage tracking is currently appended to response text (not persisted)
- No frontend in this repo; external frontend expected at `localhost:3000`

## Config

- `.env` contains all environment variables (API keys, DB credentials)
- `src/pactus_backend/shared/config.py` defines `settings` via pydantic-settings