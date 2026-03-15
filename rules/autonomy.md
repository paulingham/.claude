# Autonomy Rules

## SOLID Principles

Follow SOLID. Key applications:
- **SRP**: One service class per business operation
- **DIP**: Inject dependencies via constructor, not hard-coded class references
- **OCP**: Extend via new classes, don't modify existing ones for new features

## Error Handling

- Never fail silently — always surface errors
- Retry with exponential backoff for transient failures (HTTP, queue)
- Log errors with sufficient context: correlation ID, input params, stack trace

## Self-Sufficiency

- Validate your own work before marking tasks complete
- Run linting and tests before declaring done
