# Internationalization (i18n) Patterns

## Framework Selection

| Stack | Library | Format |
|-------|---------|--------|
| React | react-intl (FormatJS), i18next + react-i18next | ICU MessageFormat, JSON |
| Next.js | next-intl, next-i18next | ICU MessageFormat, JSON |
| Rails | Built-in I18n | YAML |
| Django | Built-in gettext | PO files |
| Node.js | i18next | JSON |
| Go | go-i18n, x/text | TOML, JSON |

## Key Structure

```
Flat keys (preferred — easier to search):
  "auth.login.title": "Sign In"
  "auth.login.email_label": "Email Address"
  "auth.login.submit": "Sign In"
  "auth.login.error.invalid": "Invalid email or password"

NOT nested (harder to find in code):
  auth: { login: { title: "Sign In" } }
```

### Naming Conventions
```
{feature}.{component}.{element}
  dashboard.header.title
  settings.profile.save_button
  errors.not_found.title
  errors.not_found.description
```

## Pluralization

Use ICU MessageFormat for correct pluralization across languages:
```
"items.count": "{count, plural, =0 {No items} one {1 item} other {{count} items}}"
```

Languages have different plural rules (Arabic has 6 forms, not just singular/plural). Never build pluralization with if/else — use the i18n library's built-in plural handling.

## Date, Time, Number Formatting

```
NEVER format dates/numbers manually. Use Intl API or i18n library.

Dates:   Intl.DateTimeFormat(locale, options)
Numbers: Intl.NumberFormat(locale, { style: 'currency', currency: 'USD' })
Relative: Intl.RelativeTimeFormat(locale) → "3 days ago"

Store dates as UTC in database.
Convert to user's timezone for display only.
```

## RTL (Right-to-Left) Support

```
Languages: Arabic, Hebrew, Farsi, Urdu

CSS:
  html[dir="rtl"] — set based on locale
  Use logical properties: margin-inline-start (not margin-left)
  Use flexbox/grid — they handle direction automatically
  Icons: some need mirroring (arrows, progress bars), some don't (play, checkmark)

Next.js:
  <html lang={locale} dir={dir}>

Testing: always test RTL layout with Arabic dummy content
```

## Translation Workflow

```
1. Developer adds key + English string in code
2. Extract keys to translation files (automatic or manual)
3. Send to translators (Crowdin, Lokalise, Phrase, POEditor)
4. Translators provide translations
5. Pull translations back into codebase
6. CI: check for missing translations (keys in code but not in translation files)
```

## Locale Detection

```
Priority order:
1. User preference (stored in profile/settings)
2. URL path or subdomain (/fr/dashboard, fr.app.com)
3. Accept-Language header (browser preference)
4. Default locale (en-US)

Persist selection: save to user profile, set cookie for unauthenticated users
```

## Testing

```
- Missing translations: lint for keys used in code but missing from translation files
- Pseudo-localization: replace strings with accented characters to catch hardcoded text
- Long strings: German/Finnish strings are ~30% longer than English — test UI overflow
- RTL: test layout with Arabic/Hebrew content
- Pluralization: test with 0, 1, 2, 5, 21 (catches languages with complex plural rules)
- Date/number formatting: test with different locales (1,234.56 vs 1.234,56)
```

## Common Anti-Patterns

```
BAD:  "Hello, " + user.name          → concatenation breaks word order in some languages
GOOD: t("greeting", { name: user.name })  → "Bonjour, {name}" works in any order

BAD:  count === 1 ? "item" : "items" → breaks for languages with > 2 plural forms
GOOD: t("items.count", { count })     → uses ICU plural rules

BAD:  moment(date).format("MM/DD/YYYY") → US-only format
GOOD: Intl.DateTimeFormat(locale).format(date) → locale-aware
```
