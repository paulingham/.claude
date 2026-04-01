# Developer Experience Patterns

## ESLint Configuration

### TypeScript + React (Next.js / Vite)

ESLint 9+ flat config (`eslint.config.mjs`):
```javascript
import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import reactPlugin from 'eslint-plugin-react';
import reactHooksPlugin from 'eslint-plugin-react-hooks';
import jsxA11yPlugin from 'eslint-plugin-jsx-a11y';
import importPlugin from 'eslint-plugin-import';

export default tseslint.config(
  js.configs.recommended,
  ...tseslint.configs.strictTypeChecked,
  reactPlugin.configs.flat.recommended,
  reactPlugin.configs.flat['jsx-runtime'],
  jsxA11yPlugin.flatConfigs.recommended,
  {
    plugins: { 'react-hooks': reactHooksPlugin, import: importPlugin },
    rules: {
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
      'import/order': ['error', {
        groups: ['builtin', 'external', 'internal', 'parent', 'sibling'],
        'newlines-between': 'always',
        alphabetize: { order: 'asc' },
      }],
      'import/no-duplicates': 'error',
    },
    settings: { react: { version: 'detect' } },
  },
  { ignores: ['node_modules/', '.next/', 'dist/', '.claude/'] },
);
```

### Node.js API (TypeScript)
Same as above minus React plugins. Add:
```javascript
// Additional rules for API projects
'no-console': ['error', { allow: ['warn', 'error'] }],
'@typescript-eslint/no-floating-promises': 'error',
```

### Ruby (RuboCop)
```yaml
# .rubocop.yml
require:
  - rubocop-rails
  - rubocop-rspec

AllCops:
  TargetRubyVersion: 3.2
  NewCops: enable
  Exclude:
    - 'db/schema.rb'
    - 'bin/*'
    - 'vendor/**/*'

Metrics/MethodLength:
  Max: 5

Metrics/ClassLength:
  Max: 50
```

### Python (Ruff)
```toml
# ruff.toml
target-version = "py312"
line-length = 100

[lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "SIM", "T20"]
# E: pycodestyle, F: pyflakes, I: isort, N: pep8-naming
# W: warnings, UP: pyupgrade, B: bugbear, SIM: simplify, T20: no print

[format]
quote-style = "double"
indent-style = "space"
```

## Prettier Configuration

```json
// .prettierrc
{
  "singleQuote": true,
  "trailingComma": "all",
  "printWidth": 100,
  "tabWidth": 2,
  "semi": true,
  "bracketSpacing": true,
  "arrowParens": "always",
  "endOfLine": "lf"
}
```

```
// .prettierignore
node_modules/
.next/
dist/
coverage/
*.min.js
pnpm-lock.yaml
package-lock.json
.claude/
```

## TypeScript Configuration

### Strict Mode (mandatory for greenfield)
```json
// tsconfig.json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,
    "forceConsistentCasingInFileNames": true,
    "isolatedModules": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "module": "ESNext",
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "jsx": "react-jsx",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src/**/*.ts", "src/**/*.tsx"],
  "exclude": ["node_modules", ".claude"]
}
```

### Multiple tsconfig Pattern
```
tsconfig.json         — base config (shared compilerOptions)
tsconfig.app.json     — application (extends base, includes src/)
tsconfig.test.json    — tests (extends base, looser settings for test utilities)
```

## Testing Infrastructure

### Vitest (preferred for new TypeScript projects)
```typescript
// vitest.config.ts
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    exclude: ['node_modules', '.claude/worktrees'],
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/test/**', 'src/**/*.d.ts'],
      thresholds: { lines: 80, branches: 80, functions: 80 },
    },
  },
  resolve: {
    alias: { '@': resolve(__dirname, './src') },
  },
});
```

### Test Setup File
```typescript
// src/test/setup.ts
import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';
import { server } from '@/mocks/server';

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => { cleanup(); server.resetHandlers(); });
afterAll(() => server.close());
```

### MSW (Mock Service Worker)
```typescript
// src/mocks/handlers.ts
import { http, HttpResponse } from 'msw';

export const handlers = [
  http.get('/api/v1/users', () => {
    return HttpResponse.json({
      data: [{ id: '1', name: 'Jane Doe', email: 'jane@example.com' }],
      meta: { page: 1, total: 1 },
    });
  }),
];

// src/mocks/server.ts (test environment)
import { setupServer } from 'msw/node';
import { handlers } from './handlers';
export const server = setupServer(...handlers);

// src/mocks/browser.ts (development environment)
import { setupWorker } from 'msw/browser';
import { handlers } from './handlers';
export const worker = setupWorker(...handlers);
```

### Testing Library Patterns
```typescript
// Prefer role queries over test IDs
screen.getByRole('button', { name: 'Submit' });  // GOOD
screen.getByTestId('submit-btn');                  // AVOID

// User event over fireEvent
const user = userEvent.setup();
await user.click(screen.getByRole('button'));      // GOOD
fireEvent.click(screen.getByRole('button'));        // AVOID

// Accessibility assertion on every component test
import { axe, toHaveNoViolations } from 'jest-axe';
expect.extend(toHaveNoViolations);

const { container } = render(<MyComponent />);
expect(await axe(container)).toHaveNoViolations();
```

### Jest (when Vitest not supported)
```typescript
// jest.config.ts
import type { Config } from 'jest';

const config: Config = {
  preset: 'ts-jest',
  testEnvironment: 'jsdom',
  setupFilesAfterSetup: ['<rootDir>/src/test/setup.ts'],
  moduleNameMapper: { '^@/(.*)$': '<rootDir>/src/$1' },
  testPathIgnorePatterns: ['node_modules', '.claude/worktrees'],
  coverageThreshold: {
    global: { branches: 80, functions: 80, lines: 80 },
  },
};
export default config;
```

## Git Hooks

### Husky + lint-staged
```bash
# Installation
npm install -D husky lint-staged @commitlint/cli @commitlint/config-conventional
npx husky init
```

```bash
# .husky/pre-commit
npx lint-staged
```

```bash
# .husky/commit-msg
npx commitlint --edit "$1"
```

```json
// package.json (add lint-staged config)
{
  "lint-staged": {
    "*.{ts,tsx}": ["eslint --fix --max-warnings=0", "prettier --write"],
    "*.{json,md,yml,yaml}": ["prettier --write"],
    "*.css": ["prettier --write"]
  }
}
```

### Commitlint
```javascript
// commitlint.config.js
export default { extends: ['@commitlint/config-conventional'] };
// Types: feat, fix, chore, docs, style, refactor, test, ci, perf, build
```

## Editor Configuration

### .editorconfig
```ini
root = true

[*]
indent_style = space
indent_size = 2
end_of_line = lf
charset = utf-8
trim_trailing_whitespace = true
insert_final_newline = true

[*.md]
trim_trailing_whitespace = false

[*.{py,rb}]
indent_size = 4
```

### VS Code Workspace Settings
```json
// .vscode/settings.json
{
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "esbenp.prettier-vscode",
  "editor.codeActionsOnSave": {
    "source.fixAll.eslint": "explicit"
  },
  "typescript.tsdk": "node_modules/typescript/lib",
  "typescript.preferences.importModuleSpecifier": "non-relative",
  "tailwindCSS.experimental.classRegex": [
    ["cva\\(([^)]*)\\)", "[\"'`]([^\"'`]*).*?[\"'`]"]
  ]
}
```

```json
// .vscode/extensions.json
{
  "recommendations": [
    "dbaeumer.vscode-eslint",
    "esbenp.prettier-vscode",
    "bradlc.vscode-tailwindcss",
    "editorconfig.editorconfig",
    "ms-vscode.vscode-typescript-next"
  ]
}
```

## Package Scripts Convention

Every project should have these standard scripts in `package.json`:
```json
{
  "scripts": {
    "dev": "[framework dev command]",
    "build": "[framework build command]",
    "start": "[production start command]",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:coverage": "vitest run --coverage",
    "lint": "eslint . --max-warnings=0",
    "lint:fix": "eslint . --fix --max-warnings=0",
    "typecheck": "tsc --noEmit",
    "format": "prettier --write .",
    "format:check": "prettier --check .",
    "prepare": "husky"
  }
}
```

## Worktree Exclusion

Test runner configs MUST exclude `.claude/worktrees/` to prevent duplicate test runs:

```typescript
// Vitest: in vitest.config.ts
test: { exclude: ['node_modules', '.claude/worktrees'] }

// Jest: in jest.config.ts
testPathIgnorePatterns: ['node_modules', '.claude/worktrees']

// Playwright: in playwright.config.ts
testIgnore: ['.claude/worktrees/**']

// Rspec: in .rspec
--exclude-pattern '.claude/**'
```
