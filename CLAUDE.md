# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an AI auto-development platform that automatically generates runnable code from requirements using multi-agent workflows. The platform consists of:

- **RAG knowledge base system** - Document retrieval and knowledge management using ChromaDB
- **Agent system** - Specialized agents for requirements, task planning, development, review, and testing
- **LangGraph workflow orchestration** - Multi-agent collaboration process control
- **OpenClaw execution engine** - Secure code execution in Docker sandbox environments
- **Skill system** - Extensible skills for building, deployment, debugging, etc.

## Development Setup

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- PostgreSQL (via Docker)
- Redis (via Docker)

### Initial Setup
1. Install dependencies using Poetry:
   ```bash
   pip install poetry
   poetry install
   ```
2. Copy environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and database settings
   ```
3. Start dependencies:
   ```bash
   docker-compose up -d postgres redis
   ```
4. Initialize database:
   ```bash
   poetry run python scripts/migrate.py
   ```

## Common Development Commands

### Running the Application
- **Start FastAPI server**: `poetry run start` (or `poetry run uvicorn api.main:app --reload`)
- **Start Celery worker**: `poetry run worker`
- **Database migrations**: `poetry run migrate` (or `poetry run python scripts/migrate.py --action create`)
- **Seed knowledge base**: `poetry run seed`

### Testing
- **Run all tests**: `poetry run pytest`
- **Run with coverage**: `poetry run pytest --cov=aid_dev_platform`
- **Run specific test**: `poetry run pytest tests/path/to/test_file.py::test_function`

### Code Quality
- **Format code**: `poetry run black .`
- **Sort imports**: `poetry run isort .`
- **Type checking**: `poetry run mypy .`
- **Linting**: `poetry run flake8 .`
- **Pre-commit hooks**: `poetry run pre-commit run --all-files`

### Database Operations
- **Create tables**: `poetry run python scripts/migrate.py --action create`
- **Drop tables**: `poetry run python scripts/migrate.py --action drop` (development only)
- **Reset database**: `poetry run python scripts/migrate.py --action reset`
- **Check connection**: `poetry run python scripts/migrate.py --action check`

## Architecture

### Core Components

#### 1. API Layer (`api/`)
- FastAPI application with REST endpoints
- Routers: requirements, tasks, projects, executions
- Middleware: logging, error handling, CORS
- Entry point: `api/main.py` creates app with startup/shutdown events

#### 2. Configuration (`config/`)
- `settings.py`: Centralized configuration using Pydantic Settings
- `agents_config.py`: Agent-specific parameters and prompt templates
- `llm_config.py`: LLM provider settings and prompt templates
- `database_config.py`: Database connection pooling settings
- `celery_config.py`: Celery task queue configuration

#### 3. Agent System (`core/agents/`)
- **BaseAgent**: Abstract base class with LLM integration and retry logic
- **Specialized agents**:
  - `requirement_agent.py`: Analyzes requirements documents
  - `task_planner.py`: Decomposes requirements into tasks
  - `development_agent.py`: Generates code using Claude Code integration
  - `review_agent.py`: Reviews code quality and security
  - `test_agent.py`: Generates and executes tests
- **AgentOrchestrator**: Coordinates agent execution
- **AgentFactory**: Creates agent instances based on configuration

#### 4. Workflow Management (`core/workflow/`)
- **WorkflowManager**: LangGraph-based workflow execution engine
- **GraphDefinitions**: Predefined workflows (development, review, test, full_development)
- **State Management**: `WorkflowState` dataclass with execution context
- Workflows are defined as LangGraph state graphs with agent nodes

#### 5. Knowledge Base (`core/knowledge_base/`)
- **VectorStore**: ChromaDB integration for document embeddings
- **Embeddings**: OpenAI and local embedding models
- **DocumentProcessor**: Splits and processes documents for RAG
- **Retrieval**: Semantic search and document retrieval
- **KnowledgeManager**: Manages document lifecycle and synchronization

#### 6. Execution Engine (`core/execution/`)
- **OpenClawExecutor**: Secure code execution in Docker containers
- Features: resource limits, timeout controls, network isolation
- Integrates with task execution system

#### 7. Queue System (`core/queue/`)
- **TaskQueue**: Celery-based asynchronous task processing
- Uses Redis as broker and result backend
- Supports task prioritization and retry mechanisms

#### 8. Services Layer (`services/`)
- Business logic services that coordinate between components
- `knowledge_service.py`: Knowledge base operations
- `requirement_service.py`: Requirement analysis pipeline
- `project_service.py`: Project management
- `task_service.py`: Task lifecycle management
- `execution_service.py`: Code execution coordination
- `queue_service.py`: Task queue management
- `workflow_service.py`: Workflow execution coordination

#### 9. Data Models (`models/`)
- SQLAlchemy ORM models in `database.py`
- Key entities: User, Project, Requirement, Task, TaskExecution, CodeArtifact, ReviewFeedback, TestResult, WorkflowExecution
- Pydantic schemas in `schemas.py` for API validation

#### 10. Utilities (`utils/`)
- `llm_client.py`: Unified LLM client for Claude/OpenAI
- `logging_config.py`: Structured logging with Loguru
- `file_utils.py`: File operations and processing

### Data Flow
1. **Requirement Input**: Documents uploaded via API → stored in knowledge base
2. **Requirement Analysis**: Requirement agent extracts structured specs
3. **Task Planning**: Task planner decomposes specs into development tasks
4. **Development Workflow**: Development agent generates code → Review agent provides feedback → Test agent creates tests
5. **Execution**: OpenClaw executor runs generated code in sandbox
6. **Results**: Code artifacts, review feedback, test results stored in database

### Key Integration Points
- **LLM Integration**: Uses both Claude and OpenAI APIs via unified client
- **Vector Database**: ChromaDB for semantic search and RAG
- **Task Queue**: Celery + Redis for asynchronous processing
- **Container Execution**: Docker for secure code execution
- **Database**: PostgreSQL with SQLAlchemy ORM

## Important Files

- `pyproject.toml`: Project dependencies and tool configurations
- `api/main.py`: FastAPI application factory
- `config/settings.py`: Central configuration with environment variables
- `core/agents/base_agent.py`: Base agent implementation
- `core/workflow/workflow_manager.py`: Workflow orchestration engine
- `models/database.py`: Database models and session management
- `scripts/migrate.py`: Database migration utilities

## Code Style

- **Formatter**: Black with 88-character line length
- **Import sorting**: isort with Black profile
- **Type checking**: mypy with Python 3.11 target
- **Linting**: flake8
- **Testing**: pytest with asyncio support and coverage reporting
- **Commit messages**: Conventional Commits (feat, fix, docs, style, refactor, test, chore)