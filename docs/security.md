# Security

Security architecture and hardening details for DocMind.

---

## Server-side Authorization

Every protected endpoint resolves the user from the JWT (`app/api/deps.py`) and enforces roles via `require_role`. Retrieval, documents, conversations, and feedback all apply ownership / visibility rules in the backend — the frontend is never trusted.

- Non-owners of a conversation or document receive a 404 (existence hidden) or 403 as appropriate.
- `STUDENT` / `FACULTY` cannot reach admin endpoints.
- The last remaining `ADMIN` cannot be demoted (`LAST_ADMIN` error).

---

## Prompt-injection Hardening

The system prompt (`app/rag/prompts.py`) treats retrieval evidence as untrusted data and instructs the model to never follow instructions embedded in it. Evidence is delimited and labelled `[n]` before it reaches the LLM.

---

## Credential Hygiene

- Passwords are bcrypt-hashed and never logged.
- Registration rejects client-supplied roles.
- Login returns the same error for an unknown email and a wrong password (no user enumeration).
- API responses never expose password hashes, storage paths, or raw stack traces (structured `{error:{code,message}}` envelope).

---

## No Secrets in Version Control

A Phase 8 secrets scan (Google API key, `sk-`-style tokens, `SECRET_KEY` / password assignments) over all tracked files found only documented dev placeholders. Real keys live only in untracked `.env` files (git-ignored).

---

## Upload Validation

PDFs are validated before any extraction:

1. File extension (must be `.pdf`)
2. MIME type check
3. `%PDF-` magic bytes verification
4. Size limit (`MAX_UPLOAD_SIZE_BYTES`, default 20 MiB)
5. Empty content rejection

A file renamed to `.pdf` that is not actually a PDF is still rejected.

---

## Production Hardening Checklist

Before deploying to a shared environment:

1. **`SECRET_KEY`** — replace with a strong random string (32+ bytes). The dev default is not secure.
2. **`POSTGRES_PASSWORD`** — replace with a strong random password.
3. **`CORS_ORIGINS`** — set to the real frontend origin(s) only. Do not use `*`.
4. **`DEBUG`** — set to `false`.
5. **`GEMINI_API_KEY`** — provide a real key and keep it out of version control.
6. **JWT storage** — the current implementation stores JWTs in `localStorage` (dev-tier persistence). A hardened deployment should move to httpOnly cookies or a secure token store to mitigate XSS risks.
7. **TLS** — put the application behind a reverse proxy (nginx / Caddy) that terminates TLS. The Docker Compose stack does not include a TLS terminator.
8. **Backups** — back up the `pgdata`, `backend_storage`, and `hf_cache` Docker volumes.
