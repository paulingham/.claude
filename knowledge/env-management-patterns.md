# Environment & Secret Management Patterns

## .env File Hierarchy

```
Loading order (later overrides earlier):
1. .env                  — shared defaults (committed as .env.example)
2. .env.{environment}    — environment-specific (development, test, staging)
3. .env.local            — local overrides (never committed)
4. .env.{environment}.local — local environment overrides (never committed)
5. Process environment   — highest priority (set by platform/CI)
```

**Git rules:**
- Commit: `.env.example` (all keys, no values, with comments)
- Never commit: `.env`, `.env.local`, `.env.*.local`, any file with real secrets

## Env Var Categories

| Category | Examples | Rotation Frequency |
|----------|---------|-------------------|
| App config | `PORT`, `LOG_LEVEL`, `NODE_ENV` | Rarely |
| Database | `DATABASE_URL`, `REDIS_URL` | On credential rotation |
| API keys (own) | `JWT_SECRET`, `ENCRYPTION_KEY` | Quarterly |
| API keys (third-party) | `STRIPE_SECRET_KEY`, `SENDGRID_API_KEY` | On compromise |
| OAuth | `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET` | On compromise |
| Infrastructure | `AWS_ACCESS_KEY_ID`, `SENTRY_DSN` | Per policy |

## Startup Validation (Fail Fast)

Validate all required env vars at application startup — not when first used.

**Node.js (Zod):**
```typescript
const envSchema = z.object({
  DATABASE_URL: z.string().url(),
  REDIS_URL: z.string().url(),
  JWT_SECRET: z.string().min(32),
  PORT: z.coerce.number().default(3000),
  NODE_ENV: z.enum(['development', 'test', 'production']),
});
export const env = envSchema.parse(process.env);
```

**Python (pydantic-settings):**
```python
class Settings(BaseSettings):
    database_url: str
    redis_url: str
    jwt_secret: str = Field(min_length=32)
    port: int = 3000
    model_config = SettingsConfigDict(env_file='.env')
```

**Rails:**
```ruby
# config/initializers/env_check.rb
%w[DATABASE_URL REDIS_URL SECRET_KEY_BASE].each do |key|
  raise "Missing required env var: #{key}" unless ENV[key].present?
end
```

## Secret Storage by Environment

| Environment | Storage | Access |
|------------|---------|--------|
| Development | `.env.local` file | Direct file read |
| CI/CD | GitHub Actions secrets / GitLab CI variables | Injected as env vars |
| Staging | Platform secrets (Fly.io, Heroku, Render) | Platform-managed |
| Production | Vault (AWS Secrets Manager, 1Password, HashiCorp Vault) | Runtime fetch or injected |

## Secret Rotation Procedure

```
1. Generate new secret value
2. Configure new value in secret store (don't remove old yet)
3. Deploy application that accepts BOTH old and new values
4. Verify application works with new value
5. Remove old value from secret store
6. Deploy to remove dual-acceptance code (if any)
```

## Environment Segregation

- Staging and production MUST use different credentials for everything
- Never share database instances, API keys, or encryption keys across environments
- CI/CD pipelines should have their own service accounts with minimal permissions
- Use environment-scoped secret stores (GitHub environment secrets, AWS parameter store paths)

## Agent Checklist

Before writing code that uses an environment variable:
1. Check `.env.example` — is this variable documented?
2. If not: add it to `.env.example` with a comment explaining its purpose
3. Add it to the startup validation schema
4. Add it to the project CLAUDE.md if it requires special setup instructions
