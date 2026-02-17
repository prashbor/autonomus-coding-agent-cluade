# Feature Name

## Introduction
Brief description of the feature to add to the existing codebase.

## Project Type
Existing repository (single)

## Jira Ticket
PROJ-123

## Existing Codebase
- Path: /path/to/your/repository
- Main entry: src/main.py (or equivalent)
- Key modules: src/api/, src/services/, src/models/
- Test location: tests/
- Test command: pytest / npm test / mvn test

## Functional Requirements
What the feature should DO (user-facing behaviors):
- FR-1: [User can do X / Feature provides Y]
- FR-2: [User can do X / Feature provides Y]
- FR-3: [User can do X / Feature provides Y]

## System Requirements
Non-functional requirements (performance, security, compatibility, etc.):
- SR-1: [Performance / Security / Compatibility requirement]
- SR-2: [Performance / Security / Compatibility requirement]

## Success Criteria
- Criterion 1: How to verify this works
- Criterion 2: How to verify this works

## Constraints
- Follow existing code patterns
- Use existing authentication/authorization
- Maintain backward compatibility

## Additional Notes
Any other context about the existing codebase the agent should know.

---

# EXAMPLE: Add Export Feature to E-Commerce API

## Introduction
Add CSV and PDF export functionality for orders and customer data to the existing e-commerce API.

## Project Type
Existing repository (single)

## Jira Ticket
ECOM-456

## Existing Codebase
- Path: /home/dev/projects/ecommerce-api
- Main entry: src/main.py
- Key modules: src/orders/, src/customers/, src/auth/
- Test location: tests/
- Test command: pytest

## Functional Requirements
What the feature should DO (user-facing behaviors):
- FR-1: Export user's orders to CSV format with all order details
- FR-2: Export user's orders to PDF format with company branding
- FR-3: Export customer list to CSV (admin only)
- FR-4: Add date range filtering for exports
- FR-5: Respect user permissions (users see own data, admins see all)

## System Requirements
Non-functional requirements (performance, security, compatibility, etc.):
- SR-1: Rate limit export endpoints to 10 requests per minute per user
- SR-2: Export files streamed (not loaded entirely in memory) for large datasets
- SR-3: Maximum export size: 10,000 records per request
- SR-4: Export endpoints respond within 5 seconds for typical datasets

## Success Criteria
- Export endpoints follow existing REST API conventions
- Tests follow existing pytest patterns with fixtures
- PDF exports include company logo and formatting
- No breaking changes to existing endpoints

## Constraints
- Follow existing code patterns (service layer, repository pattern)
- Use existing authentication middleware
- Use existing permission decorators
- Maintain backward compatibility with API v1

## Additional Notes
- The existing codebase uses SQLAlchemy for ORM
- ReportLab is already in requirements.txt for PDF generation
- Look at src/reports/ for similar export patterns
- Maximum export size should be 10,000 records
