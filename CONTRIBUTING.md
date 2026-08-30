# Contributing to Northstar

Thank you for helping improve Northstar. Bug fixes, documentation improvements, accessibility work, integration adapters, and focused product enhancements are welcome.

## Development setup

1. Fork and clone the repository.
2. Copy `.env.example` to `.env`. Never commit that file or real credentials.
3. Create a Python 3.11 virtual environment and run `pip install -r requirements.txt`.
4. Run the backend with `python -m uvicorn backend.main:app --reload --port 8000`.
5. In `frontend`, run `npm ci` and `npm run dev`.

## Before submitting

Run both required checks:

```bash
python -m pytest
npm run build --prefix frontend
```

Keep pull requests small and explain the user-visible result. Add tests for backend behavior, tenant isolation, authentication, or integration changes. Do not include `.env`, provider tokens, database files, logs, user content, or screenshots containing private data.

## Pull requests

- Create a branch from `main`.
- Use a clear title and link related issues.
- Describe testing performed and any setup changes.
- Preserve read-only integration defaults and explicit user approval for external actions.
- By contributing, you agree that your contribution is licensed under Apache License 2.0.

Please follow the [Code of Conduct](CODE_OF_CONDUCT.md). Report security problems privately as described in [SECURITY.md](SECURITY.md).
