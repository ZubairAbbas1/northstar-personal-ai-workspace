# Security Policy

## Supported Versions

Security fixes are applied to the latest code on the `main` branch. This project does not currently maintain older release lines.

## Multi-Tenant Security & Encryption

The **AI Productivity Workspace** is designed with security-first, multi-tenant isolation principles:

1. **User Isolation**:
   - Every database query, cache key, and background task is strictly scoped to the authenticated `user_id`.
   - Access control tokens are verified using signed JWTs (`HS256`).

2. **Secret Encryption at Rest**:
   - User-provided AI API keys (BYOK) and third-party OAuth access/refresh tokens are encrypted using **AES-256-GCM / Fernet symmetric encryption** before persistence.
   - Plaintext secrets are never stored, never returned in frontend API responses, and masked when displayed (e.g. `gsk_••••1234`).

3. **Read-First Integrations**:
   - Current OAuth scopes and product workflows prioritize read access. Generated replies are drafts for the user to review; the API does not silently send provider-side write actions.

4. **Production Guardrails**:
   - Production startup rejects the bundled development JWT and encryption secrets. OAuth state is signed, provider-bound, and expires after ten minutes.

## Reporting a Vulnerability

If you discover a security issue, do not open a public issue containing secrets or exploit details. Use **Security → Report a vulnerability** in this GitHub repository to submit a private report. Include the affected version, reproduction steps, impact, and any suggested mitigation.

You should receive an initial response within seven days. Please allow time for a fix before publicly disclosing the issue.
