# API Reference

Full endpoint documentation for DocMind. Interactive OpenAPI docs are also available at `/docs` (Swagger) and `/redoc` on the running backend.

---

## Authentication

### `POST /api/auth/register`

Create a new account. Always creates a `STUDENT`; any client-supplied role is rejected.

**Body** (JSON):
```json
{
  "name": "Jane Doe",
  "email": "jane@example.com",
  "password": "strongpassword"
}
```

**Response:** the new user (no token).

### `POST /api/auth/login`

Issue a JWT. Uses `application/x-www-form-urlencoded` (OAuth2 password form, so Swagger UI's "Authorize" button works).

**Body:** `username` + `password` (form fields).

**Response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": { "id": "...", "name": "...", "email": "...", "role": "STUDENT" }
}
```

### `GET /api/auth/me`

Returns the current user. Requires `Authorization: Bearer <token>`.

### Auth Details

- Roles are stored uppercase: `STUDENT`, `FACULTY`, `ADMIN`.
- Endpoints declare required roles via `require_role` dependencies; access is enforced server-side.
- Tokens: HS256 signed with `SECRET_KEY`, expiry `ACCESS_TOKEN_EXPIRE_MINUTES` (default 60).
- On the frontend the token lives in `localStorage` under `docmind_token`.

### Auth Error Codes

`AUTHENTICATION_REQUIRED`, `INVALID_CREDENTIALS`, `INVALID_TOKEN`, `TOKEN_EXPIRED`, `EMAIL_ALREADY_REGISTERED`, `FORBIDDEN`

---

## Documents

All document endpoints require authentication.

### `POST /api/documents`

Upload a PDF. Accepts `multipart/form-data`:
- `file` (required): the PDF file
- `title`, `description`, `department`, `category`, `effective_date` (optional)

**Validation:**
- Rejects non-PDF files by extension, MIME type, or `%PDF-` magic bytes (`INVALID_DOCUMENT_TYPE`)
- Rejects empty files (`EMPTY_DOCUMENT`)
- Rejects files over `MAX_UPLOAD_SIZE_BYTES` (`DOCUMENT_TOO_LARGE`)

### `GET /api/documents`

List documents visible to the current user.

### `GET /api/documents/{id}`

Document detail including chunk count.

### `PATCH /api/documents/{id}`

Edit metadata. Immutable fields (status, uploader, storage paths) cannot be changed.

### `DELETE /api/documents/{id}`

Delete document, its chunks, and stored file. Only the uploader or an `ADMIN` can delete.

### `POST /api/documents/{id}/process`

Trigger ingestion. Document lifecycle: `UPLOADED → PROCESSING → ACTIVE`. Failures leave the document `FAILED` with a safe internal error. Reprocessing replaces old chunks (safe to retry).

### Document Visibility

A document is visible when the user uploaded it or its `access_level` matches their role (`PUBLIC` is viewable by everyone). Only the uploader or an `ADMIN` may edit, process, or delete.

### Document Error Codes

`DOCUMENT_NOT_FOUND`, `FORBIDDEN`, `INVALID_DOCUMENT_TYPE`, `EMPTY_DOCUMENT`, `DOCUMENT_TOO_LARGE`, `DOCUMENT_PROCESSING_FAILED`

---

## Document Versions

### `GET /api/documents/{id}/versions`

List all versions of a document.

### `POST /api/documents/{id}/versions`

Upload a new version. Archives the previous current version and switches the document's file pointers. The new version is `UPLOADED` until `POST /{id}/process` makes it `ACTIVE`.

---

## Chat & Search

Both endpoints require authentication and are permission-aware server-side.

### `POST /api/chat`

Ask a grounded question (RAG).

**Body:**
```json
{
  "message": "What is the minimum attendance requirement?",
  "conversation_id": null
}
```

**Response:**
```json
{
  "answer": "The minimum attendance requirement is 75%.",
  "citations": [
    {
      "document_id": "...",
      "document_title": "Examination Ordinance 2026",
      "page_number": 14,
      "section": "Attendance",
      "relevance_score": 0.91
    }
  ],
  "conversation_id": "...",
  "message_id": "..."
}
```

When no evidence meets the retrieval thresholds, or evidence is below `CONFIDENCE_THRESHOLD`, the answer is the fixed grounded fallback: *"I couldn't find sufficient information in the available university documents."* (The LLM is skipped).

If the LLM provider fails (e.g. rate limits or unavailability), the endpoint returns a `503 Service Unavailable` with `LLM_RATE_LIMITED` or `LLM_UNAVAILABLE` rather than defaulting to the grounded fallback.

With `conversation_id` omitted, a new conversation is created and the exchange is persisted.

### `POST /api/search`

Developer/debug endpoint. Returns raw hybrid retrieval results without calling an LLM.

Each result exposes per-stage scores: `dense_score`, `bm25_score`, `hybrid_score`, `rerank_score`.

### `POST /api/search/results`

User-facing search. Same retrieval as `/api/search` but returns clean results: `document_title`, `page_number`, `section`, `snippet`, `relevance_score` — no raw scores or chunk ids.

### Chat Error Codes

`MESSAGE_EMPTY`, `MESSAGE_TOO_LONG`, `CONVERSATION_NOT_FOUND`, `LLM_RATE_LIMITED`, `LLM_UNAVAILABLE`

### LLM Provider

Selected by `LLM_PROVIDER`: `gemini` (default; requires `GEMINI_API_KEY`) or `local` (offline development provider — answers verbatim from the top chunk, never for production).

---

## Conversations

### `GET /api/conversations`

List the current user's conversations.

### `GET /api/conversations/{id}`

Full conversation thread with citations. Ownership enforced server-side; non-owners get 404.

### `DELETE /api/conversations/{id}`

Delete a conversation. Ownership enforced.

---

## Feedback

### `POST /api/feedback`

Rate an assistant answer 1–5 with an optional reason.

```json
{
  "message_id": "...",
  "rating": 4,
  "reason": "Helpful answer with good citations"
}
```

One entry per (user, message) via unique constraint — resubmission upserts. Only assistant messages can be rated, and only the conversation owner can rate them.

---

## Admin

All admin endpoints require the `ADMIN` role.

### `GET /api/admin/users`

List all users. Responses never include password hashes.

### `GET /api/admin/documents`

List all documents. Responses never include storage paths.

### `GET /api/admin/stats`

System statistics (real DB counts: users, documents, conversations, etc.).

### `PATCH /api/admin/users/{id}/role`

Change a user's role. The last remaining `ADMIN` cannot be demoted (`LAST_ADMIN` error).

---

## Demo (Demo Mode Only)

These endpoints are only available when `DEMO_MODE=true`.

### `GET /api/demo/info`

Demo metadata: mode status, index readiness, document title, chunk count.

### `POST /api/demo/chat`

Grounded demo chat scoped to the pre-indexed PDF. Unauthenticated.

```json
{
  "message": "What were the retrieval metrics?"
}
```

---

## Error Response Format

All errors use a consistent envelope:

```json
{
  "error": {
    "code": "DOCUMENT_PROCESSING_FAILED",
    "message": "The document could not be processed."
  }
}
```

Provider errors specifically return HTTP 503 with the following structure:
```json
{
  "error": {
    "code": "LLM_RATE_LIMITED",
    "message": "The AI service is temporarily rate limited. Please try again shortly."
  }
}
```

No raw stack traces are ever returned.
