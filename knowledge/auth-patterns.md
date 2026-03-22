# Authentication & Authorization Patterns

## Strategy Selection

| Approach | When | Stack Examples |
|----------|------|---------------|
| Session-based (cookie) | Server-rendered apps, same-origin SPA | Rails Devise, Django auth, Express + express-session |
| JWT + refresh token | API-first, mobile clients, cross-origin | Node.js custom, FastAPI, Go |
| OAuth 2.0 / OIDC | Social login, SSO, enterprise federation | Passport.js, OmniAuth, django-allauth |
| API keys | Machine-to-machine, webhooks | Custom middleware |

## Registration Flow

```
1. Validate input (email format, password strength, uniqueness)
2. Hash password (bcrypt, argon2 — NEVER MD5/SHA1)
3. Create user record (email_verified: false)
4. Generate verification token (cryptographically random, time-limited: 24h)
5. Send verification email with token link
6. On verification: set email_verified: true, invalidate token
```

**Password requirements:** Minimum 8 characters. Check against breached password lists (HaveIBeenPwned API). No arbitrary complexity rules (uppercase, special char) — length matters more.

## Login Flow

```
1. Find user by email (case-insensitive lookup)
2. Check account lockout status (see Brute Force Protection)
3. Verify password hash (constant-time comparison)
4. On failure: increment failed_attempts, check lockout threshold
5. On success: reset failed_attempts, create session/token
6. Set session cookie (httpOnly, Secure, SameSite=Strict) OR return JWT
```

## Brute Force Protection

```
- Track failed_attempts and locked_until per account
- Lock after 5 consecutive failures for 15 minutes
- Rate limit login endpoint: 5 requests per 15 minutes per IP + account
- CAPTCHA after 3 failures (reCAPTCHA v3 or hCaptcha)
- Log all auth events (success, failure, lockout) for audit trail
```

## Password Reset Flow

```
1. User requests reset by email
2. Generate cryptographically random token (32+ bytes)
3. Store hashed token with expiry (1 hour max)
4. Send reset email with one-time link
5. On reset: validate token (not expired, not used), hash new password
6. Invalidate ALL existing sessions for this user
7. Mark token as used (prevent replay)
```

**Security:** Always return "If an account exists, we've sent a reset email" — never confirm/deny account existence.

## Session Management

### Cookie-Based Sessions
```
Cookie flags: httpOnly, Secure, SameSite=Strict
Session store: Redis or database (never in-memory in production)
Session rotation: generate new session ID after login (prevent fixation)
Session expiry: sliding window (30 min idle timeout, 24h absolute max)
Logout: delete server-side session + clear cookie
```

### JWT + Refresh Token
```
Access token:  short-lived (15 minutes), stored in memory (never localStorage)
Refresh token: long-lived (7-30 days), stored in httpOnly cookie
Rotation:      issue new refresh token on each refresh (detect replay)
Revocation:    maintain a denylist of revoked tokens (Redis with TTL)
Claims:        { sub: user_id, role: "admin", iat, exp } — minimal claims
```

**Token delivery:**
- Access token: returned in response body, held in memory by SPA
- Refresh token: set as httpOnly/Secure/SameSite cookie
- Never store tokens in localStorage or sessionStorage (XSS vulnerable)

## RBAC (Role-Based Access Control)

```
Principles:
- Deny by default — explicitly grant permissions
- Check at middleware level (before controller/handler)
- Object-level authorization: verify the user owns the resource
- Scope database queries by user permissions (never trust client IDs)
```

### Implementation Pattern
```
1. Define roles: admin, manager, member, viewer
2. Define permissions: users:read, users:write, reports:read, billing:manage
3. Map roles to permissions (many-to-many)
4. Middleware: extract user from session/token → load permissions → check
5. Controller: verify specific permission before each action
6. Query scoping: WHERE tenant_id = current_user.tenant_id
```

### Stack Examples

**Rails (Devise + Pundit):**
```ruby
# Gemfile: gem 'devise', gem 'pundit'
# User model: devise :database_authenticatable, :registerable, :recoverable
# Policy: class PostPolicy; def update?; user.admin? || record.author == user; end; end
# Controller: authorize @post
```

**Node.js (Passport + custom RBAC):**
```javascript
// passport.use(new LocalStrategy(...))
// Middleware: requireAuth, requireRole('admin')
// Object-level: if (resource.userId !== req.user.id) throw new ForbiddenError()
```

**Django (django-allauth + django-guardian):**
```python
# settings.py: INSTALLED_APPS += ['allauth', 'guardian']
# views.py: @permission_required('app.change_post')
# Object-level: get_objects_for_user(request.user, 'app.view_post')
```

## OAuth 2.0 / Social Login

```
1. Register app with provider (Google, GitHub, etc.)
2. Redirect user to provider's auth URL with state parameter (CSRF protection)
3. Provider redirects back with authorization code
4. Exchange code for access token (server-side, never client-side)
5. Fetch user profile from provider API
6. Find-or-create local user record (match by provider + provider_user_id)
7. Create local session
```

**Security:**
- Always verify the `state` parameter matches what you sent
- Exchange the code server-side (never expose client_secret to the browser)
- Store provider tokens encrypted if you need ongoing API access

## Multi-Factor Authentication (MFA)

```
TOTP (Time-based One-Time Password):
- Generate secret key, store encrypted per user
- Present QR code for authenticator app setup
- Verify 6-digit code with time window tolerance (±30s)
- Provide backup codes (10 single-use, stored hashed)

When to require MFA:
- After password login (step-up auth)
- Sensitive operations (password change, role change, payment)
- New device/location detection
```

## Security Checklist

- [ ] Passwords hashed with bcrypt (cost 12+) or argon2id
- [ ] Session IDs are cryptographically random (128+ bits)
- [ ] Cookies: httpOnly, Secure, SameSite=Strict
- [ ] Token storage: never localStorage, use httpOnly cookies or memory
- [ ] Failed login rate limiting (IP + account)
- [ ] Account lockout after 5 consecutive failures
- [ ] Password reset tokens: hashed, time-limited, single-use
- [ ] Session invalidation on password change
- [ ] CSRF protection on all state-changing requests
- [ ] Auth events logged (login, logout, failure, lockout, password change)
