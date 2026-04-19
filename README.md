# Manos AI

**Manos AI** is a Modular Adaptive Network Operating System for learning. It treats learning like an operating system: modular (instance-based subjects), adaptive (performance-driven learning), network (connected knowledge), and OS (core system orchestrating workflows).

## System Overview

Manos AI provides an intelligent learning platform that adapts to individual performance, offering personalized education through modular subject instances. The system processes documents, generates questions, manages flashcards with spaced repetition, and conducts adaptive tests while providing comprehensive analytics.

## Core Features

- **Multiple Learning Instances**: Isolated subject workspaces for focused learning
- **Document Ingestion**: PDF and text file processing with automatic content extraction
- **AI-Powered Content Generation**: Q&A generation with difficulty levels, flashcard creation
- **Adaptive Learning**: Spaced repetition for flashcards, performance-driven test scheduling
- **Performance Analytics**: Accuracy tracking, topic-wise analysis, weak area identification
- **Manual Content Creation**: Support for custom Q&A and flashcard creation

## Architecture Overview

The system follows a clean, layered architecture:

- **Backend (FastAPI)**: REST API with business logic orchestration
- **AI Modules**: Independent pure logic components for ML/AI operations
- **Database Layer**: PostgreSQL with SQLAlchemy ORM
- **Instance Isolation**: Per-subject data isolation in `data/instances/{instance_id}/`

## Tech Stack

- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL
- **AI**: Ollama (local LLM integration)
- **Containerization**: Docker
- **Frontend**: React/TypeScript (existing)

## How to Run

1. Ensure Docker and Docker Compose are installed
2. Clone the repository
3. Navigate to the project root
4. Copy backend environment template:
   ```bash
   cp backend/.env.example backend/.env
   ```
5. Configure your `.env` file with database and Ollama settings
6. Start the services:
   ```bash
   docker-compose up
   ```
7. Backend will be available at `http://localhost:8000`
8. Frontend at `http://localhost:8080` (run separately)

## High-Level System Flow

1. **Instance Creation**: User creates a learning instance (subject workspace)
2. **Document Upload**: PDFs/text files ingested and processed
3. **Content Generation**: AI extracts text, chunks content, generates Q&A pairs
4. **Learning Activities**: Flashcards with spaced repetition, adaptive tests
5. **Performance Tracking**: Evaluation scores feed analytics and scheduling
6. **Adaptive Adjustments**: System adapts difficulty and timing based on performance

## API Endpoints

- `GET/POST /instances` - Instance management
- `POST /instances/{id}/ingest` - Document upload
- `GET /instances/{id}/flashcards/due` - Due flashcards
- `POST /tests/{id}/submit` - Test submission
- `GET /instances/{id}/analytics` - Performance data

## Development

- Backend code in `backend/src/`
- AI modules in `backend/src/ai/` (independent logic)
- Database models in `backend/src/models/`
- API schemas in `backend/src/schemas/`

## Contributing

1. Follow the modular architecture principles
2. Maintain separation of concerns
3. Ensure AI modules remain independent
4. Add comprehensive comments to all files
5. Test with instance isolation in mind