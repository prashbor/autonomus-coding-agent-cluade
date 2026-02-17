# Feature Name

## Introduction
Brief description of the feature that spans multiple repositories.

## Project Type
Multi-repository

## Jira Ticket
PROJ-456

## Repositories

### 1. Repository Name (e.g., Database)
- Path: /path/to/first/repository
- Language: SQL / Python / etc.
- Purpose: What this repo handles
- Test command: How to run tests

### 2. Repository Name (e.g., Backend API)
- Path: /path/to/second/repository
- Language: Java / Python / TypeScript / etc.
- Framework: Spring Boot / FastAPI / Express / etc.
- Purpose: What this repo handles
- Test command: mvn test / pytest / npm test

### 3. Repository Name (e.g., Frontend)
- Path: /path/to/third/repository
- Language: TypeScript / JavaScript
- Framework: React / Vue / Angular
- Purpose: What this repo handles
- Test command: npm test

## Cross-Repo Dependencies
- Repository 1 must be completed before Repository 2
- Repository 2 must be completed before Repository 3

## Functional Requirements
What the feature should DO (user-facing behaviors):
- FR-1: [User can do X / Feature provides Y]
- FR-2: [User can do X / Feature provides Y]
- FR-3: [User can do X / Feature provides Y]

## System Requirements
Non-functional requirements (performance, security, compatibility, etc.):
- SR-1: [Performance / Security / Compatibility requirement]
- SR-2: [Performance / Security / Compatibility requirement]

## Repository-Specific Tasks
- Repo 1: What changes are needed
- Repo 2: What changes are needed
- Repo 3: What changes are needed

## Success Criteria
- Criterion 1: How to verify end-to-end
- Criterion 2: How to verify end-to-end

## Additional Notes
Any coordination details or shared conventions across repos.

---

# EXAMPLE: User Activity Tracking Feature

## Introduction
Add comprehensive user activity tracking across the platform. Track user actions in the database, expose them via API, and display them in a dashboard.

## Project Type
Multi-repository

## Jira Ticket
TRACK-789

## Repositories

### 1. Database (PostgreSQL)
- Path: /repos/company-database
- Language: SQL (PostgreSQL)
- Purpose: Database schema, migrations, and stored procedures
- Test command: psql -f tests/run_tests.sql

### 2. Backend API (Python)
- Path: /repos/backend-api
- Language: Python 3.11
- Framework: FastAPI
- Purpose: REST API endpoints and business logic
- Test command: pytest

### 3. Frontend Dashboard (TypeScript)
- Path: /repos/frontend-dashboard
- Language: TypeScript
- Framework: React 18 + Vite
- Purpose: User interface and data visualization
- Test command: npm test

## Cross-Repo Dependencies
- Database must be completed before Backend API (API needs the tables)
- Backend API must be completed before Frontend (UI needs the endpoints)

## Functional Requirements
What the feature should DO (user-facing behaviors):
- FR-1: Track user actions (page views, button clicks, form submissions)
- FR-2: Display activity feed with real-time updates
- FR-3: Provide activity statistics dashboard with charts
- FR-4: Allow filtering activities by date range and type
- FR-5: Enable activity data export (admin only)

## System Requirements
Non-functional requirements (performance, security, compatibility, etc.):
- SR-1: Activity recording adds <10ms latency to user actions
- SR-2: Dashboard loads activity data within 500ms
- SR-3: Real-time updates appear within 1 second
- SR-4: Activity data retained for 90 days, then archived
- SR-5: GDPR compliant: activities deletable per user on request

## Repository-Specific Tasks
- Database:
  - Create user_activities table with columns: id, user_id, action_type, metadata, created_at
  - Add indexes on user_id and created_at for query performance
  - Create a view for activity aggregation by user

- Backend API:
  - POST /api/activities - Record a new activity
  - GET /api/activities - List activities with pagination and filters
  - GET /api/activities/stats - Get activity statistics
  - WebSocket endpoint for real-time activity feed

- Frontend:
  - ActivityFeed component showing recent activities
  - ActivityDashboard page with charts and statistics
  - Real-time updates via WebSocket connection
  - Filter by date range and activity type

## Success Criteria
- End-to-end flow works: action in UI -> API -> Database -> back to UI
- All repositories have passing tests
- Activity tracking works across all layers without errors

## Additional Notes
- Use the shared company ESLint config in frontend
- Backend should use existing auth middleware from src/middleware/auth.py
- Database migrations should be numbered sequentially (next is 042_)
- Activity types should be defined as an enum in all three repos
- Consider GDPR: activities should be deletable per user
