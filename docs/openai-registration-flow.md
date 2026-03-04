# OpenAI Registration Technical Flow

## Overview

OpenAI uses **OAuth2 + PKCE** (Proof Key for Code Exchange) for authentication.
Registration is embedded within the OAuth authorization flow, triggered by `prompt=signup`.

## Architecture

| Component | URL | Role |
|-----------|-----|------|
| ChatGPT Frontend | chatgpt.com | Session init, CSRF, callback |
| Auth Server | auth.openai.com | OAuth2 authorize, registration UI |
| Token Server | auth0.openai.com | OAuth2 token exchange |
| Next-Auth | chatgpt.com/api/auth/* | CSRF management, provider routing |

## PKCE Parameters

| Parameter | Description |
|-----------|-------------|
| `code_verifier` | Random 43-128 char string (base64url) |
| `code_challenge` | `BASE64URL(SHA256(code_verifier))` |
| `code_challenge_method` | `S256` |
| `client_id` | OpenAI OAuth client ID (TBD: extract from page) |
| `redirect_uri` | ChatGPT callback URL |
| `scope` | OAuth scopes requested |
| `state` | Anti-CSRF state parameter |
| `nonce` | Replay protection |

## Complete Registration Flow (10 Steps)

### Phase 1: Session Initialization

#### Step 1 — GET chatgpt.com

Establish browser session and extract Next-Auth CSRF token.

```
GET https://chatgpt.com/
```

**Extract from response:**
- Cookies: `__Secure-next-auth.session-token`, `__Host-next-auth.csrf-token`, etc.
- CSRF token: from cookie `__Host-next-auth.csrf-token` or page meta tag

---

#### Step 2 — POST signin/login-web

Initiate OAuth flow through Next-Auth provider routing.

```
POST https://chatgpt.com/api/auth/signin/login-web
Content-Type: application/x-www-form-urlencoded

csrfToken=<csrf_token>&callbackUrl=/&json=true
```

**Response:**
```json
{
  "url": "https://auth.openai.com/authorize?client_id=...&redirect_uri=...&scope=...&response_type=code&code_challenge=...&code_challenge_method=S256&prompt=login&state=..."
}
```

**Key:** The `url` field contains the OAuth authorize URL. For registration, modify `prompt=login` → `prompt=signup`.

---

### Phase 2: OAuth Authorize

#### Step 3 — GET authorize (signup)

Navigate to OpenAI's auth server with signup prompt.

```
GET https://auth.openai.com/authorize?
    client_id=<client_id>
    &redirect_uri=<redirect_uri>
    &scope=<scope>
    &response_type=code
    &code_challenge=<code_challenge>
    &code_challenge_method=S256
    &prompt=signup
    &state=<state>
    &nonce=<nonce>
```

**Extract from response:**
- Registration page HTML/state
- Internal session cookies for auth.openai.com
- Any hidden form fields (state tokens, etc.)

---

### Phase 3: Account Creation

These steps happen on `auth.openai.com` internal APIs.
Exact endpoint paths TBD — need to capture from browser DevTools.

#### Step 4 — Submit Email

```
POST https://auth.openai.com/<TBD: signup endpoint>
Content-Type: application/json

{
  "email": "user@example.com",
  "state": "<from_step_3>"
}
```

**Purpose:** Submit registration email. Server checks if email is available.

---

#### Step 5 — Submit Password

```
POST https://auth.openai.com/<TBD: password endpoint>
Content-Type: application/json

{
  "password": "<password>",
  "state": "<session_state>"
}
```

**Purpose:** Set account password. Must meet OpenAI password requirements (min 8 chars).

---

#### Step 6 — Solve Turnstile Challenge

Cloudflare Turnstile verification integrated into the registration page.

```
Turnstile Parameters:
- sitekey: <TBD: extract from page>
- pageurl: https://auth.openai.com/...
- action: (if any)

Capsolver API:
POST https://api.capsolver.com/createTask
{
  "clientKey": "<capsolver_api_key>",
  "task": {
    "type": "AntiTurnstileTaskProxyLess",
    "websiteURL": "https://auth.openai.com/...",
    "websiteKey": "<turnstile_sitekey>"
  }
}
```

**Result:** Turnstile token to include in subsequent requests.

---

#### Step 7 — Wait for Email Verification Code

OpenAI sends a verification code to the registered email.

```
Integration: TalentMail API
1. Create temp email (Step 1 of pipeline)
2. Poll inbox: GET /api/pool/{mailbox_id}/emails
3. Auto-extract verification_code from response

Verification Code Format:
- 6-digit numeric code
- Sent from: noreply@openai.com (or similar)
- Subject: likely contains "Verify" or "验证"
```

---

#### Step 8 — Submit Verification Code

```
POST https://auth.openai.com/<TBD: verify endpoint>
Content-Type: application/json

{
  "code": "<6_digit_code>",
  "state": "<session_state>"
}
```

**Purpose:** Verify email ownership.

---

#### Step 9 — Submit Profile (Name + Age)

```
POST https://auth.openai.com/<TBD: profile endpoint>
Content-Type: application/json

{
  "name": "<full_name>",
  "birthday": "<YYYY-MM-DD>"
}
```

**Purpose:** Complete profile. Age must be 13+ (OpenAI ToS).

---

### Phase 4: Token Exchange

#### Step 10 — OAuth Callback

After registration completes, auth.openai.com redirects back to ChatGPT.

```
GET https://chatgpt.com/api/auth/callback/login-web?
    code=<authorization_code>
    &state=<state>
```

ChatGPT backend exchanges the authorization code for tokens:

```
POST https://auth0.openai.com/oauth/token
Content-Type: application/json

{
  "grant_type": "authorization_code",
  "code": "<authorization_code>",
  "redirect_uri": "<redirect_uri>",
  "client_id": "<client_id>",
  "code_verifier": "<code_verifier>"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGc...",
  "refresh_token": "...",
  "id_token": "...",
  "token_type": "Bearer",
  "expires_in": 86400
}
```

---

## Flow Diagram

```
User                ChatGPT                auth.openai.com         auth0.openai.com
 │                    │                         │                        │
 │── GET / ──────────>│                         │                        │
 │<── CSRF+cookies ───│                         │                        │
 │                    │                         │                        │
 │── POST signin ────>│                         │                        │
 │<── authorize URL ──│                         │                        │
 │                    │                         │                        │
 │── GET authorize?prompt=signup ──────────────>│                        │
 │<── registration page + state ────────────────│                        │
 │                    │                         │                        │
 │── POST email ───────────────────────────────>│                        │
 │<── ok ───────────────────────────────────────│                        │
 │                    │                         │                        │
 │── POST password ────────────────────────────>│                        │
 │<── ok + turnstile challenge ─────────────────│                        │
 │                    │                         │                        │
 │── solve turnstile (Capsolver) ──>            │                        │
 │<── turnstile token ──────────────            │                        │
 │                    │                         │                        │
 │  ~~~ wait for email verification code ~~~    │                        │
 │  ~~~ (TalentMail polls inbox) ~~~            │                        │
 │                    │                         │                        │
 │── POST verification code ───────────────────>│                        │
 │<── ok ───────────────────────────────────────│                        │
 │                    │                         │                        │
 │── POST name + age ──────────────────────────>│                        │
 │<── redirect to callback ─────────────────────│                        │
 │                    │                         │                        │
 │── GET callback?code=xxx ───>│                │                        │
 │                    │── POST token exchange ──────────────────────────>│
 │                    │<── access_token + refresh_token ─────────────────│
 │<── session set ────│                         │                        │
```

## External Service Dependencies

| Service | Purpose | Required |
|---------|---------|----------|
| TalentMail | Temp email + verification code extraction | Yes |
| Capsolver | Turnstile CAPTCHA solving | Yes |
| HTTP Proxy | Access OpenAI from restricted regions | Depends on location |

## Configuration Required

```yaml
# config/settings.yaml
openai:
  register_url: 'https://chatgpt.com'
  auth_url: 'https://auth.openai.com'
  token_url: 'https://auth0.openai.com'
  client_id: ''          # TBD: extract from OAuth flow
  redirect_uri: ''       # TBD: extract from OAuth flow
  scope: ''              # TBD: extract from OAuth flow

capsolver:
  api_key: ''
  turnstile_sitekey: ''  # TBD: extract from registration page

proxy:
  enabled: false
  url: 'socks5://127.0.0.1:7897'

talentmail:
  base_url: 'http://localhost/api'
  email: ''
  password: ''
```

## Information Still Needed

To implement Steps 4-9, we need the actual API endpoints.
Capture method: Browser DevTools > Network tab > walk through registration manually.

- [ ] auth.openai.com internal API paths for email/password/verify/profile submission
- [ ] OAuth2 client_id, redirect_uri, scope values
- [ ] Turnstile sitekey
- [ ] Request/response body formats for each step
- [ ] Any additional headers (x-openai-*, etc.)
