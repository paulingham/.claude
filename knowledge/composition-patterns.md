# Composition Patterns

## The Boolean Prop Anti-Pattern

### The Problem
```tsx
// 5 booleans = 32 possible states. Most combinations are untested.
<Card
  isCompact={true}
  showHeader={false}
  showFooter={true}
  isInline={true}
  hideAvatar={false}
/>
```

Each boolean doubles the testing surface. With 5 booleans, you'd need 32 test cases for full coverage. In practice, most combinations are never tested and produce unexpected layouts.

### The Rule

**Maximum 3 boolean props per component.** If you need a 4th, refactor to compound components or explicit variants.

**No `show*` or `hide*` props.** If a section is optional, use compound children — the parent renders what's passed to it.

## Compound Component Pattern

### When to Use
- Component has 3+ visual sections
- Multiple layout variants are needed
- Users need to rearrange or omit sections
- Component API is growing beyond 8 props

### Anatomy
```tsx
// Instead of: <Card showHeader showFooter isCompact />
// Use:
<Card>
  <Card.Header>Project Settings</Card.Header>
  <Card.Body>...</Card.Body>
  <Card.Footer>
    <Button variant="ghost">Cancel</Button>
    <Button>Save</Button>
  </Card.Footer>
</Card>

// Compact variant: just use a different composition
<Card.Compact>
  <Card.Body>Inline content</Card.Body>
</Card.Compact>
```

### Implementation with React Context
```tsx
// card-context.ts
const CardContext = createContext<{ variant: string }>({ variant: 'default' });

// card.tsx — parent provides context
function Card({ variant = 'default', children }: CardProps) {
  return (
    <CardContext value={{ variant }}>
      <div className={cardVariants({ variant })}>{children}</div>
    </CardContext>
  );
}

// card-header.tsx — child consumes context
function CardHeader({ children }: { children: ReactNode }) {
  const { variant } = use(CardContext); // React 19+ use() hook
  return <div className={headerVariants({ variant })}>{children}</div>;
}

// Attach sub-components
Card.Header = CardHeader;
Card.Body = CardBody;
Card.Footer = CardFooter;
Card.Compact = CardCompact;
```

### Common Compound Components
```
Card       → Card.Header, Card.Body, Card.Footer, Card.Compact
Table      → Table.Header, Table.Row, Table.Cell, Table.Footer
Dialog     → Dialog.Trigger, Dialog.Content, Dialog.Title, Dialog.Close
Select     → Select.Trigger, Select.Content, Select.Item, Select.Group
Accordion  → Accordion.Item, Accordion.Trigger, Accordion.Content
Tabs       → Tabs.List, Tabs.Trigger, Tabs.Content
Alert      → Alert.Title, Alert.Description, Alert.Action
Navigation → Nav.Group, Nav.Item, Nav.Separator
```

## Explicit Variant Pattern (CVA)

### Instead of Boolean Flags → Named Variants
```tsx
// BAD: boolean combinatorics
<Button small primary disabled rounded />

// GOOD: explicit, self-documenting variants
<Button variant="primary" size="sm" state="disabled" shape="pill" />
```

### CVA Implementation
```tsx
import { cva, type VariantProps } from 'class-variance-authority';

const buttonVariants = cva(
  'inline-flex items-center justify-center font-medium transition-colors focus-visible:ring-2',
  {
    variants: {
      variant: {
        primary: 'bg-primary text-primary-foreground hover:bg-primary/90',
        secondary: 'bg-secondary text-secondary-foreground hover:bg-secondary/80',
        destructive: 'bg-destructive text-destructive-foreground hover:bg-destructive/90',
        ghost: 'hover:bg-accent hover:text-accent-foreground',
        link: 'text-primary underline-offset-4 hover:underline',
      },
      size: {
        sm: 'h-8 px-3 text-xs rounded-md',
        md: 'h-10 px-4 text-sm rounded-md',
        lg: 'h-12 px-6 text-base rounded-lg',
        icon: 'h-10 w-10 rounded-md',
      },
    },
    defaultVariants: { variant: 'primary', size: 'md' },
  }
);

type ButtonProps = VariantProps<typeof buttonVariants> & ComponentProps<'button'>;
```

### Variant Exhaustiveness
Every visual state should be a named variant. If you find yourself combining booleans to create a visual state, it should be a variant instead:

```tsx
// BAD: boolean-derived visual state
const className = isActive && isPrimary ? 'bg-blue-600' : isActive ? 'bg-gray-600' : '';

// GOOD: explicit variant
variant: {
  active: 'bg-primary text-primary-foreground',
  inactive: 'bg-muted text-muted-foreground',
  activeSecondary: 'bg-secondary text-secondary-foreground',
}
```

## Provider Pattern

### For Theme/Config Propagation
```tsx
// theme-provider.tsx
function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<'light' | 'dark'>('system');
  return (
    <ThemeContext value={{ theme, setTheme }}>
      {children}
    </ThemeContext>
  );
}

// Any descendant can read/update theme without prop drilling
function ThemeToggle() {
  const { theme, setTheme } = use(ThemeContext);
  return <Button onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} />;
}
```

### When to Use Provider
- Value is consumed by many distant descendants
- Value changes infrequently (theme, locale, auth state)
- Avoids prop drilling more than 2 levels deep

### When NOT to Use Provider
- Value changes frequently (typing, animations, mouse position)
- Only 1-2 consumers exist (just pass props)
- Server state (use TanStack Query instead)

## Slot Pattern

### For Flexible Insertion Points
```tsx
// The parent defines WHERE content goes; the consumer decides WHAT goes there
function PageLayout({ header, sidebar, children, footer }: LayoutSlots) {
  return (
    <div className="grid grid-rows-[auto_1fr_auto] min-h-screen">
      <header>{header}</header>
      <div className="grid grid-cols-[240px_1fr]">
        <aside>{sidebar}</aside>
        <main>{children}</main>
      </div>
      <footer>{footer}</footer>
    </div>
  );
}

// Usage: consumer fills the slots
<PageLayout
  header={<TopNav />}
  sidebar={<DashboardNav />}
  footer={<StatusBar />}
>
  <DashboardContent />
</PageLayout>
```

## Render Delegation

### For Fully Customizable Rendering
```tsx
// Component handles logic; consumer controls rendering
function Combobox<T>({ items, renderItem, onSelect }: ComboboxProps<T>) {
  const [query, setQuery] = useState('');
  const filtered = items.filter(matchesQuery(query));
  return (
    <div>
      <Input value={query} onChange={setQuery} />
      <ul>{filtered.map(item => renderItem(item, onSelect))}</ul>
    </div>
  );
}

// Usage
<Combobox
  items={users}
  renderItem={(user, select) => (
    <li onClick={() => select(user)}>
      <Avatar src={user.avatar} /> {user.name}
    </li>
  )}
  onSelect={handleSelect}
/>
```

## Anti-Patterns Checklist

Before completing any component work, verify:
- [ ] No component has more than 3 boolean props
- [ ] No prop named `show*` or `hide*` — use compound children instead
- [ ] No `is*` props that affect layout — use explicit variants
- [ ] No deeply nested ternaries in JSX — extract to compound children
- [ ] Complex components use compound pattern (3+ visual sections)
- [ ] All visual states are named variants, not boolean combinations
- [ ] Provider pattern used only for infrequently-changing values
- [ ] Props are not drilled more than 2 levels deep (extract to hook or context)

## React 19+ Notes

```
- Skip forwardRef: refs are regular props in React 19+
- use() hook replaces useContext(): const value = use(MyContext)
- Server Components by default: add "use client" only when needed
- Actions: form actions replace onSubmit handlers for mutations
```
