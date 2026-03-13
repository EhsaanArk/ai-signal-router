# Design System

This document defines the visual language for the SageMaster Signal Copier dashboard. The system is built on **Tailwind CSS** with **shadcn/ui** components, ensuring consistency without a heavy design tool dependency.

## 1. Design Principles

1. **Clarity over decoration** — Traders need to scan information quickly. Every element must earn its space.
2. **Density where it matters** — Tables and logs should be compact. Forms and onboarding should breathe.
3. **Status at a glance** — Use color-coded badges and indicators so users can assess system health without reading text.
4. **Progressive disclosure** — Show the simple path first (channel → webhook → save). Reveal advanced options (symbol mappings, risk overrides) on demand.

## 2. Color Palette

Built on a neutral base with semantic accent colors. Uses CSS custom properties for dark mode support.

### Base Colors (Neutral)

| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `--background` | `#FFFFFF` | `#09090B` | Page background |
| `--foreground` | `#09090B` | `#FAFAFA` | Primary text |
| `--card` | `#FFFFFF` | `#0A0A0C` | Card surfaces |
| `--muted` | `#F4F4F5` | `#27272A` | Subtle backgrounds, disabled states |
| `--muted-foreground` | `#71717A` | `#A1A1AA` | Secondary text, placeholders |
| `--border` | `#E4E4E7` | `#27272A` | Borders, dividers |

### Brand Colors

| Token | Value | Usage |
|-------|-------|-------|
| `--primary` | `#2563EB` (Blue 600) | Primary buttons, active nav items, links |
| `--primary-foreground` | `#FFFFFF` | Text on primary buttons |
| `--accent` | `#EFF6FF` (Blue 50) | Hover backgrounds, selected rows |

### Semantic Colors

| Token | Value | Usage |
|-------|-------|-------|
| `--success` | `#16A34A` (Green 600) | Connected status, successful signals, "Active" badge |
| `--warning` | `#D97706` (Amber 600) | Pending states, tier limit approaching |
| `--destructive` | `#DC2626` (Red 600) | Errors, failed signals, delete actions, "Disconnected" badge |
| `--info` | `#2563EB` (Blue 600) | Informational toasts, tips |

## 3. Typography

Using the system font stack for performance. No custom fonts to load.

```css
--font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
--font-mono: "SF Mono", "Fira Code", "Fira Mono", "Roboto Mono", monospace;
```

### Type Scale

| Element | Size | Weight | Line Height | Usage |
|---------|------|--------|-------------|-------|
| Page Title | `text-2xl` (24px) | `font-semibold` (600) | 1.33 | Page headings: "Routing Rules", "Signal Logs" |
| Section Title | `text-lg` (18px) | `font-semibold` (600) | 1.5 | Card headers, form sections |
| Body | `text-sm` (14px) | `font-normal` (400) | 1.5 | Default text, table cells, form labels |
| Caption | `text-xs` (12px) | `font-normal` (400) | 1.5 | Timestamps, helper text, badge labels |
| Code / Signals | `text-sm` (14px) | `font-mono` | 1.5 | Raw signal text, webhook URLs, channel IDs |

## 4. Spacing & Layout

### Grid
- Max content width: `max-w-6xl` (1152px), centered.
- Dashboard uses a sidebar layout: 240px sidebar + fluid content area.
- On mobile (`< md`): sidebar collapses to a hamburger menu.

### Spacing Scale
Follow Tailwind's default 4px base scale:
- Between form fields: `space-y-4` (16px)
- Between sections/cards: `space-y-6` (24px)
- Card internal padding: `p-6` (24px)
- Page padding: `px-6 py-8` on desktop, `px-4 py-6` on mobile

## 5. Component Specifications

### 5.1 Sidebar Navigation

```
┌──────────────────────┐
│  ◆ Signal Copier     │  ← Logo + app name
│                      │
│  ▸ Dashboard         │  ← Active: blue bg, bold text
│  ▸ Telegram          │
│  ▸ Routing Rules     │
│  ▸ Signal Logs       │
│                      │
│  ─────────────────   │
│  ▸ Settings          │
│  ▸ Log Out           │
│                      │
│  ┌────────────────┐  │
│  │ Starter Plan   │  │  ← Current tier badge
│  │ 1/2 Rules Used │  │  ← Usage indicator
│  │ [Upgrade]      │  │
│  └────────────────┘  │
└──────────────────────┘
```

- Width: 240px fixed
- Background: `--card`
- Active item: `--accent` background, `--primary` text
- Icons: Lucide, 18px, left of label

### 5.2 Status Badges

| Status | Color | Text |
|--------|-------|------|
| Connected | Green (`--success`) bg, green text | "Connected" |
| Disconnected | Red (`--destructive`) bg, red text | "Disconnected" |
| Active | Green | "Active" |
| Inactive | Gray (`--muted`) bg, muted text | "Inactive" |
| Success | Green | "Success" |
| Failed | Red | "Failed" |
| Ignored | Gray | "Ignored" |

Implementation: `<Badge variant="success">Connected</Badge>`

### 5.3 Routing Rules Table

```
┌────────────────────────────────────────────────────────────────────┐
│ Routing Rules                                          [+ New Rule] │
├──────────────────┬──────────────────┬─────────┬────────┬──────────┤
│ Source Channel   │ Destination      │ Version │ Status │ Actions  │
├──────────────────┼──────────────────┼─────────┼────────┼──────────┤
│ Forex VIP Signals│ ...deals_idea/a1 │ V2      │ Active │ ✏️ 🗑️    │
│ Gold Room        │ ...deals_idea/b2 │ V2      │ Active │ ✏️ 🗑️    │
│ Gold Room        │ ...deals_idea/c3 │ V1      │Inactive│ ✏️ 🗑️    │
└──────────────────┴──────────────────┴─────────┴────────┴──────────┘
```

- Webhook URLs are truncated with `truncate` class, full URL shown in tooltip.
- Status column uses the badge component.
- Actions: Edit opens a slide-over panel; Delete shows a confirmation dialog.
- Empty state: Illustration + "No routing rules yet. Create your first rule to start copying signals."

### 5.4 Signal Logs Table

```
┌──────────────────────────────────────────────────────────────────────┐
│ Signal Logs                                          [Filter ▾]      │
├────────────────┬──────────────────────────────┬─────────┬───────────┤
│ Time           │ Signal                       │ Channel │ Status    │
├────────────────┼──────────────────────────────┼─────────┼───────────┤
│ 2 min ago      │ BUY EURUSD @ 1.1000 SL...   │ Forex.. │ ✓ Success │
│ 5 min ago      │ SELL GOLD @ 2000 SL 1990...  │ Gold R..│ ✓ Success │
│ 12 min ago     │ "Great week everyone! 🎉"    │ Forex.. │ — Ignored │
│ 1 hr ago       │ BUY NAS100 @ 18500...        │ Gold R..│ ✗ Failed  │
└────────────────┴──────────────────────────────┴─────────┴───────────┘
```

- Click a row to expand and show: parsed data JSON, webhook payload, error message (if failed).
- Pagination: "Load more" button at bottom (infinite scroll optional in V2).
- Relative timestamps (`2 min ago`) with exact timestamp in tooltip.

### 5.5 Telegram Connection Card

**Disconnected state:**
```
┌──────────────────────────────────────────┐
│  📡 Telegram Connection                  │
│                                          │
│  Status: 🔴 Disconnected                │
│                                          │
│  Connect your Telegram account to start  │
│  receiving signals from your channels.   │
│                                          │
│  Phone Number: [+1 ____________]         │
│                          [Send Code →]   │
└──────────────────────────────────────────┘
```

**Connected state:**
```
┌──────────────────────────────────────────┐
│  📡 Telegram Connection                  │
│                                          │
│  Status: 🟢 Connected                   │
│  Phone:  +1 234 567 8900                 │
│  Since:  March 10, 2026                  │
│                                          │
│                         [Disconnect]     │
└──────────────────────────────────────────┘
```

### 5.6 Create Routing Rule Wizard

A stepped form inside a full-width card (not a modal — too much content):

```
Step 1 of 3: Select Source Channel
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Choose a Telegram channel to copy signals from:

  ○ Forex VIP Signals      (-100123456789)
  ● Gold Room Premium      (-100987654321)
  ○ Crypto Calls           (-100555666777)

                               [Next →]
```

```
Step 2 of 3: Set Destination
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Paste your SageMaster webhook URL:

  Webhook URL: [https://api.sagemaster.io/deals_idea/... ]

  Payload Version:  ○ V1    ● V2 (Recommended)

                        [← Back]  [Next →]
```

```
Step 3 of 3: Symbol Mappings (Optional)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Map provider symbols to your broker symbols:

  GOLD    →  [XAUUSD     ]  [✕]
  NAS100  →  [USTEC      ]  [✕]
                     [+ Add Mapping]

                        [← Back]  [Save Rule]
```

## 6. Responsive Breakpoints

| Breakpoint | Width | Layout Change |
|-----------|-------|--------------|
| `sm` | 640px | Stack form fields |
| `md` | 768px | Sidebar collapses to hamburger; tables scroll horizontally |
| `lg` | 1024px | Full sidebar + content layout |
| `xl` | 1280px | Max content width caps at 1152px |

## 7. Motion & Feedback

- **Page transitions**: None (React Router handles instant client-side navigation).
- **Toast notifications**: Slide in from top-right, auto-dismiss after 5 seconds. Use for: rule saved, signal dispatched, errors.
- **Loading states**: Skeleton loaders (shadcn/ui `<Skeleton>`) for tables and cards during data fetch.
- **Button loading**: Spinner icon replaces button text during async operations. Button is disabled.
- **Destructive confirmations**: Delete actions always show a `<AlertDialog>` with the item name: "Delete routing rule for Forex VIP Signals → Bot 1?"

## 8. Dark Mode

- Supported via Tailwind's `dark:` variant and `class` strategy.
- Toggle in the header (sun/moon icon).
- Preference saved to `localStorage` and respected on reload.
- Default: follows system preference (`prefers-color-scheme`).

## 9. Accessibility

- All interactive elements must be keyboard navigable.
- Form inputs must have associated `<label>` elements.
- Color alone must not convey status — badges include text labels alongside color.
- Minimum contrast ratio: 4.5:1 for body text, 3:1 for large text (WCAG 2.1 AA).
- Focus rings: visible `ring-2 ring-primary` on all focusable elements.
