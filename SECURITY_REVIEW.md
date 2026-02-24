# AWS Ops Agent — Security Review

## CRITICAL Issues

### 1. No Authentication on Any Endpoint
**File:** `ops_agent/dashboard/server.py`
**Risk:** CRITICAL
**Detail:** Every API endpoint (`/api/scan/*`, `/api/remediate`, `/api/chat`, `/api/org-scan`) is completely unauthenticated. Anyone who can reach the server can:
- Delete EBS volumes, stop EC2 instances, deactivate IAM keys via `/api/remediate`
- Trigger org-wide scans that assume roles into every member account
- Send arbitrary prompts to Bedrock via `/api/chat`

**Recommendation:** Add API key auth at minimum. For production: Cognito or IAM auth via ALB.

---

### 2. CORS Allows All Origins
**File:** `ops_agent/dashboard/server.py` line: `allow_origins=["*"]`
**Risk:** HIGH
**Detail:** Any website can make cross-origin requests to the dashboard. Combined with no auth, this means a malicious page could trigger remediations if a user has the dashboard running locally.

**Recommendation:** Restrict to `["http://127.0.0.1:8080", "http://localhost:8080"]` or the ALB domain.

---

### 3. Org-Scan Sets Global Environment Variables (Race Condition)
**File:** `ops_agent/cli.py` lines 95-110, `ops_agent/dashboard/server.py` org-scan handler
**Risk:** HIGH
**Detail:** Cross-account credentials are injected via `os.environ`, which is process-global. If two org-scans run concurrently (or a scan + a chat request), credentials from one account could leak into another request's AWS calls.

**Recommendation:** Pass credentials directly via boto3 Session objects instead of env vars. The `assume_role_session` function already returns creds — use them to create a session, not pollute the environment.

---

### 4. No Input Validation on Chat Messages
**File:** `ops_agent/dashboard/chat.py`, `ops_agent/dashboard/server.py`
**Risk:** HIGH
**Detail:**
- No message length limit — a user could send a 10MB message, which gets forwarded to Bedrock
- No content filtering — prompt injection attacks could manipulate the system prompt
- No rate limiting — could rack up Bedrock costs quickly
- Chat history is not maintained server-side, so the client controls the full context

**Recommendation:**
- Cap message length (e.g., 4000 chars)
- Add rate limiting (e.g., 10 requests/minute per IP)
- Sanitize control characters
- Consider server-side conversation history

---

### 5. Hardcoded Bedrock Model ARN with Account ID
**File:** `ops_agent/dashboard/chat.py`, `ops_agent/skills/arch_diagram.py`
**Risk:** MEDIUM
**Detail:** `BEDROCK_MODEL_ID` contains a hardcoded AWS account ID (`073369242087`). This:
- Won't work in other accounts
- Leaks the developer's account ID
- Should use the model ID without the account-specific inference profile ARN

**Recommendation:** Use `anthropic.claude-haiku-4-5-20251001-v1:0` or make it configurable via env var.

---

## HIGH Issues

### 6. Remediation Has No Confirmation Server-Side
**File:** `ops_agent/dashboard/remediation.py`
**Risk:** HIGH
**Detail:** The remediation endpoint executes destructive actions (delete volumes, stop instances, revoke SG rules) with a single POST request. The "confirmation" only exists in the frontend JavaScript. A direct API call bypasses it entirely.

**Recommendation:** Implement a two-step flow: POST to create a pending remediation, then POST to confirm/execute it. Or require a confirmation token.

---

### 7. Silent Exception Swallowing
**Files:** All skills, `ops_agent/notify.py`
**Risk:** MEDIUM
**Detail:** Nearly every AWS API call is wrapped in `try/except Exception: pass`. This means:
- Permission errors are silently ignored
- API throttling goes unnoticed
- Partial scan results appear complete when they're not
- Debugging is nearly impossible

**Recommendation:** Log exceptions at WARNING level minimum. Track error counts in SkillResult (already has `errors` field but many skills don't populate it).

---

### 8. No Rate Limiting on Any Endpoint
**File:** `ops_agent/dashboard/server.py`
**Risk:** MEDIUM
**Detail:** No rate limiting on scan, remediate, or chat endpoints. An attacker or misconfigured client could:
- Trigger hundreds of concurrent scans, overwhelming AWS API limits
- Spam Bedrock chat, running up costs
- Execute mass remediations

**Recommendation:** Add `slowapi` or similar rate limiting middleware.

---

### 9. No Audit Trail for Remediations
**File:** `ops_agent/dashboard/remediation.py`
**Risk:** MEDIUM
**Detail:** Remediation actions are logged via Python `logger` but there's no persistent audit trail. If someone deletes 50 EBS volumes, there's no durable record of who did it or when (beyond CloudTrail, which shows the IAM role, not the dashboard user).

**Recommendation:** Write remediation actions to a file or DynamoDB table with timestamp, action, resource, and requester info.

---

### 10. No HTTPS Enforcement
**File:** `ops_agent/dashboard/server.py`, `Dockerfile`
**Risk:** MEDIUM
**Detail:** The server runs on plain HTTP. AWS credentials, scan results, and chat messages are transmitted in cleartext. If deployed on a network (not just localhost), this is a significant risk.

**Recommendation:** For non-localhost deployments, require HTTPS via ALB termination or add TLS to uvicorn.

---

## MEDIUM Issues

### 11. Findings Data Sent to Bedrock Without Filtering
**File:** `ops_agent/dashboard/chat.py`
**Detail:** All scan findings (including resource IDs, account IDs, security group configs) are sent to Bedrock as context. If using a shared/cross-region inference profile, this data leaves the account boundary.

**Recommendation:** Document this clearly. Consider allowing users to opt out of sending findings to chat.

---

### 12. No Health Check Endpoint
**File:** `ops_agent/dashboard/server.py`
**Detail:** No `/api/health` or `/healthz` endpoint for ALB target group health checks or monitoring.

**Recommendation:** Add a simple health endpoint.

---

### 13. Static Assets Served Without Cache Headers or CSP
**File:** `ops_agent/dashboard/server.py`, `index.html`
**Detail:** No Content-Security-Policy header, no X-Frame-Options, no X-Content-Type-Options. The dashboard could be embedded in an iframe for clickjacking.

**Recommendation:** Add security headers middleware.

---

### 14. Frontend Loads External Scripts
**File:** `ops_agent/dashboard/static/index.html`
**Detail:** Mermaid.js is loaded from `cdn.jsdelivr.net` and fonts from `d1.awsstatic.com`. If either CDN is compromised, the dashboard is vulnerable to XSS.

**Recommendation:** Bundle mermaid.js locally or add SRI (Subresource Integrity) hashes.

---

### 15. Chat Frontend Renders HTML from AI Response
**File:** `ops_agent/dashboard/static/js/components.js` — `formatChatResponse()`
**Detail:** The `formatChatResponse` function converts markdown-like syntax to HTML and injects it via `innerHTML`. While it escapes `<` and `>`, the bold/code replacements could potentially be exploited if Bedrock returns crafted content.

**Recommendation:** Use a proper markdown sanitizer or render as text-only.

---

## LOW Issues

### 16. In-Memory Job Store
**Detail:** All scan jobs and results are stored in memory. A server restart loses everything. Not a security issue per se, but affects reliability.

### 17. No Request Size Limits
**Detail:** FastAPI default allows large request bodies. The `/api/chat` and `/api/remediate` endpoints accept arbitrary JSON.

### 18. Notification Webhook URL Not Validated
**File:** `ops_agent/notify.py`
**Detail:** Slack webhook URL is used directly in `requests.post()` without validation. Could be used for SSRF if the URL is user-controlled.

---

## Summary

| Severity | Count | Key Areas |
|----------|-------|-----------|
| CRITICAL | 1 | No authentication |
| HIGH | 5 | CORS, env var race condition, no input validation, no server-side confirmation, exception swallowing |
| MEDIUM | 5 | No rate limiting, no audit trail, no HTTPS, data to Bedrock, no health check |
| LOW | 3 | In-memory store, no request limits, webhook SSRF |
