# Project Name

## Introduction
Brief description of what you want to build.

## Project Type
New project (create from scratch)

## Tech Stack
- Language: Python / TypeScript / Java / etc.
- Framework: FastAPI / Express / Spring Boot / etc.
- Database: PostgreSQL / SQLite / MongoDB / etc.
- Other: Redis, Docker, etc.

## Functional Requirements
What the system should DO (user-facing features and behaviors):
- FR-1: [User can do X / System provides Y]
- FR-2: [User can do X / System provides Y]
- FR-3: [User can do X / System provides Y]

## System Requirements
Non-functional requirements (performance, security, scalability, etc.):
- SR-1: [Performance / Security / Scalability requirement]
- SR-2: [Performance / Security / Scalability requirement]
- SR-3: [Performance / Security / Scalability requirement]

## Success Criteria
- Criterion 1: How to verify this works
- Criterion 2: How to verify this works

## Additional Notes
Any other context, constraints, or preferences the agent should know about.

---

# EXAMPLE: Task Manager API

## Introduction
A REST API for managing tasks with user authentication, task assignment, and due date tracking.

## Project Type
New project (create from scratch)

## Tech Stack
- Language: Python 3.9+
- Framework: FastAPI
- Database: SQLite
- Authentication: JWT tokens

## Functional Requirements
What the system should DO (user-facing features and behaviors):
- FR-1: User registration and login with JWT tokens
- FR-2: CRUD operations for tasks (create, read, update, delete)
- FR-3: Task assignment to users
- FR-4: Task filtering by status (pending, in_progress, completed)
- FR-5: Due date tracking with overdue detection
- FR-6: Input validation and proper error handling

## System Requirements
Non-functional requirements (performance, security, scalability, etc.):
- SR-1: API response time < 200ms for all endpoints
- SR-2: JWT tokens expire after 24 hours for security
- SR-3: Password hashing using bcrypt with minimum 12 rounds
- SR-4: Rate limiting: 100 requests per minute per user

## Success Criteria
- All endpoints return proper HTTP status codes
- Authentication protects all task endpoints
- Unit tests cover core functionality with >80% coverage
- API documentation auto-generated via OpenAPI/Swagger

## Additional Notes
- Keep the code simple and well-documented
- Follow PEP 8 style guidelines
- Use Pydantic for request/response models
