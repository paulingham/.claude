# Data Visualization Patterns

## Chart Selection Matrix

| Question | Chart Type | When |
|----------|-----------|------|
| How does X compare to Y? | Bar | Few categories (<12) |
| | Grouped bar | Sub-categories within categories |
| | Horizontal bar | Long category labels |
| How does X change over time? | Line | Continuous trend |
| | Area | Volume/magnitude over time |
| | Sparkline | Inline trend (KPI cards) |
| What's the breakdown of X? | Donut | 2-5 segments (NEVER pie with >5) |
| | Stacked bar | Breakdown over time |
| | Treemap | Hierarchical breakdown |
| How is X distributed? | Histogram | Frequency distribution |
| | Box plot | Statistical summary (median, quartiles) |
| How are X and Y related? | Scatter | Correlation |
| | Bubble | Correlation + third variable (size) |
| | Heatmap | Dense correlation matrix |
| What's the flow? | Funnel | Conversion steps |
| | Sankey | Flow between categories |

### Never Use
```
- 3D charts (distorts perception)
- Pie charts with >5 slices (impossible to compare)
- Dual-axis charts (confusing — use two separate charts)
- Gauge charts (inefficient use of space — use a number + bar)
```

## Library Selection

| Library | Best For | React | RN | SSR |
|---------|---------|-------|-----|-----|
| Recharts | Most SaaS dashboards | ✓ | ✗ | ✓ |
| Tremor | Tailwind-native dashboards | ✓ | ✗ | ✓ |
| Nivo | Beautiful, interactive charts | ✓ | ✗ | ✓ |
| Victory | Cross-platform (React + RN) | ✓ | ✓ | ✓ |
| D3.js | Full custom visualizations | ✓ | ✗ | ✗ |
| Chart.js | Simple, lightweight | ✓ | ✗ | ✗ |

**Default: Recharts for web, Victory for cross-platform, Tremor if already using Tailwind.**

## Dashboard Layout

### KPI Row (Top of Page)
```
┌──────────┬──────────┬──────────┬──────────┐
│  Revenue │  Users   │  Orders  │  NPS     │
│  $42.5K  │  1,234   │  567     │  72      │
│  ↑ 12%   │  ↑ 8%    │  ↓ 3%   │  → 0%    │
│  ▁▂▃▅▇█  │  ▁▂▃▄▅▆  │  █▇▅▃▂▁  │  ▃▃▃▃▃▃  │
└──────────┴──────────┴──────────┴──────────┘

Each KPI card:
  - Metric label (top)
  - Current value (large, bold)
  - Delta vs previous period (with ↑↓→ and color)
  - Sparkline (last 7 data points, no axis labels)
```

### Chart Grid
```
Standard layouts:
  2/3 + 1/3:  Hero chart (line/area) + supporting chart (donut/bar)
  1/2 + 1/2:  Two equal charts
  1/3 + 1/3 + 1/3:  Three small charts
  Full width:  Data table or complex visualization

Always:
  - Consistent height within a row
  - Filter bar above charts (shared filters)
  - Date range selector (top-right, affects all charts)
  - Same color coding across charts on the same page
```

## Chart Design Rules

### Axes
```
Y-axis: always start at zero for bar charts
X-axis: label every Nth tick to avoid overlap
Axis labels: concise, with units (Revenue ($K), Users (thousands))
Grid lines: horizontal only, subtle (muted color, 1px, dashed or dotted)
```

### Labels and Legends
```
Prefer direct labels over legends:
  Put the label next to the data (annotation on the line/bar)
  Legends: only when direct labels would clutter

Legend position: top or right, never bottom (scroll hides it)
Max 5-7 series per chart (more = unreadable)
```

### Color
```
Sequential palette: single hue, varying lightness (for continuous data)
  Revenue by month: light blue → dark blue

Categorical palette: distinct hues (for discrete categories)
  Channels: blue (web), green (mobile), purple (voice), orange (device)

Consistent: same color = same category across ALL charts on the page
Accessible: use patterns/shapes alongside color (color-blind safe)
```

### Tooltips
```
Show on hover (desktop) or tap (mobile)
Content: exact value, formatted (not raw number)
Position: above/beside the data point, never obscuring other data
Format: "March 15, 2026: $12,450 revenue (+8% vs prev period)"
```

## Real-Time Data Visualization

```
WebSocket-fed charts:
  - Buffer updates (batch every 1s, not every message)
  - Animate new data points in (slide from right for time series)
  - Fixed time window (show last 5 minutes, scroll left as new data arrives)
  - "Live" indicator (pulsing dot + "Live" label)
  - Pause/resume control (freeze chart for inspection)
  - Historical context (zoom out to see last hour/day)

Performance:
  - Limit rendered data points (downsample for large windows)
  - Use requestAnimationFrame for smooth updates
  - Canvas rendering for >1000 data points (SVG for <1000)
```

## Accessible Charts

```
Structure:
  - role="img" on chart container
  - aria-label describing the trend ("Revenue trending upward, $42K this month, up 12%")
  - Provide data table alternative (toggle: "View as table")

Interaction:
  - Keyboard navigation for data points (arrow keys)
  - Focus indicator on selected data point
  - Screen reader announcement on focus ("March 2026, $12,450")

Color:
  - Never convey meaning by color alone
  - Use patterns (dashed, dotted, solid lines) alongside colors
  - Test with color-blind simulators (Chromatic Aberration, Deuteranopia)

Text:
  - Axis labels are actual text (not rendered in SVG/Canvas without aria)
  - Sufficient contrast for labels and annotations
```

## Responsive Charts

```
Mobile:
  - Simplify: fewer data points, fewer series
  - Horizontal scroll for wide time-series
  - Larger touch targets for data points
  - Tooltip appears above finger (not under it)
  - Consider switching to summary view (KPI + sparkline instead of full chart)

Breakpoint strategy:
  Desktop (>1024px): full chart with all features
  Tablet (768-1024px): same chart, reduced margins
  Mobile (<768px): simplified chart or KPI summary
```

## Anti-Patterns

```
- Rainbow colors (no semantic meaning, hard to distinguish)
- Unlabeled axes (what am I looking at?)
- Truncated Y-axis on bar charts (misleading proportions)
- Animated chart on page load (distracting, delays comprehension)
- Too many series (>7 lines on one chart = unreadable)
- Tooltip with too much data (show key value, not a data dump)
- Chart without a title (every chart needs a clear heading)
```
