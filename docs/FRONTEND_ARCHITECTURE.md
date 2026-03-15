# Frontend Architecture

## 1. Tech Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Framework** | Vite 8 + React 19 | Lightning-fast HMR, no SSR complexity — the app is a pure SPA. React Router DOM provides client-side routing via `createBrowserRouter`. |
| **Language** | TypeScript 5 | Type safety across API contracts and component props. |
| **Styling** | Tailwind CSS 4 (via `@tailwindcss/vite`) + shadcn/ui (New York style) | Utility-first CSS keeps bundle small; shadcn/ui provides accessible, composable primitives (Dialog, Table, Toast, Form) without a heavy runtime. |
| **State Management** | TanStack Query (React Query) v5 | Handles server state (caching, revalidation, optimistic updates). No global store needed — app is predominantly server-driven. |
| **Forms** | React Hook Form + Zod | Performant form handling with schema-based validation that mirrors backend Pydantic models. |
| **HTTP Client** | Native `fetch` | Thin typed wrapper in `lib/api.ts`. No axios needed. |
| **Auth** | JWT stored in `localStorage` | Auth context pattern — `AuthProvider` wraps the app, `ProtectedRoute` component guards authenticated routes. No middleware or cookies. |
| **Icons** | Lucide React | Tree-shakeable, consistent icon set that pairs well with shadcn/ui. |
| **Charts** (V3) | Recharts | Lightweight, composable charting for the analytics dashboard. |

## 2. Directory Structure

```
frontend/
├── public/
│   └── logo.svg
├── src/
│   ├── components/
│   │   ├── ui/                       # shadcn/ui primitives (Button, Card, Dialog, etc.)
│   │   ├── forms/                    # Domain-specific forms
│   │   │   ├── TelegramConnectForm.tsx
│   │   │   ├── RoutingRuleWizard.tsx
│   │   │   └── (step components)
│   │   ├── tables/
│   │   │   ├── RoutingRulesTable.tsx
│   │   │   ├── SignalLogsTable.tsx
│   │   │   └── LogDetailRow.tsx
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx
│   │   │   ├── Header.tsx
│   │   │   ├── MobileNav.tsx
│   │   │   ├── DashboardLayout.tsx   # Sidebar + header shell (wraps dashboard routes)
│   │   │   ├── AuthLayout.tsx        # Minimal layout for login/register
│   │   │   └── ProtectedRoute.tsx    # Redirects to /login if no valid JWT
│   │   └── shared/
│   │       ├── TierGate.tsx          # Wraps features behind tier checks
│   │       ├── StatusBadge.tsx       # success/failed/ignored badges
│   │       ├── EmptyState.tsx
│   │       ├── ErrorBoundary.tsx
│   │       ├── NotFound.tsx
│   │       └── LoadingSpinner.tsx
│   ├── contexts/
│   │   └── auth-context.tsx          # AuthProvider + useAuth hook
│   ├── hooks/
│   │   ├── use-theme.ts             # Dark mode toggle
│   │   ├── use-telegram.ts          # TanStack Query hooks for Telegram status
│   │   ├── use-routing-rules.ts     # TanStack Query hooks for routing rules
│   │   ├── use-channels.ts          # TanStack Query hooks for channel list
│   │   └── use-logs.ts             # TanStack Query hooks for signal logs
│   ├── lib/
│   │   ├── api.ts                    # Typed fetch wrapper for backend API
│   │   ├── auth.ts                   # JWT localStorage helpers
│   │   ├── constants.ts              # API base URL, tier limits, etc.
│   │   ├── utils.ts                  # General utility functions (cn, formatters)
│   │   └── tier.ts                   # Tier comparison logic
│   ├── pages/                        # Route page components
│   │   ├── login.tsx
│   │   ├── register.tsx
│   │   ├── dashboard.tsx
│   │   ├── telegram.tsx
│   │   ├── routing-rules.tsx
│   │   ├── routing-rules-new.tsx
│   │   ├── logs.tsx
│   │   └── settings.tsx
│   ├── types/
│   │   └── api.ts                    # TypeScript interfaces matching backend models
│   ├── App.tsx                       # Router config (createBrowserRouter)
│   ├── main.tsx                      # React root (ReactDOM.createRoot)
│   └── index.css                     # Tailwind directives + CSS custom properties
├── vite.config.ts
├── components.json                   # shadcn/ui config
├── tsconfig.json
├── tsconfig.app.json
├── tsconfig.node.json
├── package.json
└── .env                              # VITE_API_URL=http://localhost:8000
```

## 3. Routing & Page Map

Routes are defined in `App.tsx` using React Router DOM's `createBrowserRouter`:

| Route | Page | Auth Required | Description |
|-------|------|:---:|-------------|
| `/login` | Login | No | Email + password login |
| `/register` | Register | No | Create account |
| `/` | Dashboard | Yes | Overview — Telegram status, active rules count, recent logs |
| `/telegram` | Telegram | Yes | Connect/disconnect Telegram account |
| `/routing-rules` | Rules List | Yes | View, toggle, delete routing rules |
| `/routing-rules/new` | Create Rule | Yes | Step-by-step wizard: channel → webhook → mappings |
| `/logs` | Signal Logs | Yes | Paginated table of processed signals |
| `/settings` | Settings | Yes | Email, password, subscription tier |

Auth-required routes are wrapped with a `<ProtectedRoute>` component that checks for a valid JWT in `localStorage` and redirects to `/login` if absent. Dashboard routes share a `<DashboardLayout>` (sidebar + header). Auth routes use a minimal `<AuthLayout>`.

## 4. State Management Strategy

### Server State (TanStack Query)
All data from the backend API is server state. TanStack Query handles:
- **Caching**: Routing rules and Telegram status are cached and revalidated on window focus.
- **Optimistic Updates**: Toggling a routing rule's `is_active` status updates the UI immediately, rolling back on error.
- **Pagination**: Signal logs use cursor-based pagination via `useInfiniteQuery`.

### Client State
Minimal client state — only:
- **Auth context**: Current user + JWT token (from `localStorage`), exposed via `AuthProvider` and `useAuth` hook.
- **Form state**: Managed by React Hook Form, scoped to each form component.
- **UI state**: Sidebar open/closed, modal visibility — colocated in component `useState`.

No Redux, Zustand, or global store is needed.

## 5. API Integration

### Typed API Client (`lib/api.ts`)

A thin wrapper around `fetch` that:
1. Prepends `VITE_API_URL` (defaults to `http://localhost:8000`).
2. Attaches the JWT token from `localStorage` as `Authorization: Bearer <token>`.
3. Throws typed errors for 401 (redirect to login), 403 (tier limit), 4xx/5xx.
4. Returns typed responses matching `types/api.ts`.

### API Types (`types/api.ts`)

TypeScript interfaces that mirror the backend Pydantic models:

```typescript
interface RoutingRule {
  id: string;
  source_channel_id: string;
  source_channel_name: string;
  destination_webhook_url: string;
  payload_version: "V1" | "V2";
  symbol_mappings: Record<string, string>;
  risk_overrides: Record<string, number>;
  is_active: boolean;
}

interface TelegramChannel {
  channel_id: string;
  channel_name: string;
}

interface SignalLog {
  id: string;
  channel_name: string;
  raw_message: string;
  status: "success" | "failed" | "ignored";
  processed_at: string;
}

interface AuthResponse {
  access_token: string;
  token_type: "bearer";
}
```

## 6. Authentication Flow

1. **Login/Register**: POST to `/api/v1/auth/login` or `/api/v1/auth/register`. Backend returns a JWT.
2. **localStorage Storage**: The frontend stores the JWT in `localStorage` via helpers in `lib/auth.ts`.
3. **Auth Context**: `AuthProvider` in `contexts/auth-context.tsx` loads the token on mount, exposes `user`, `login`, `logout`, and `isAuthenticated` via React context.
4. **Route Protection**: `<ProtectedRoute>` component checks `isAuthenticated` from auth context. If false, redirects to `/login` via React Router's `<Navigate>`.
5. **API Requests**: The `lib/api.ts` client reads the token from `localStorage` and sends it as `Authorization: Bearer <token>`.
6. **Logout**: Clears the token from `localStorage`, resets auth context, and navigates to `/login`.

## 7. Key UI Patterns

### Tier Gating
The `<TierGate>` component wraps features behind subscription checks:
- Checks the user's `subscription_tier` against the required tier.
- If insufficient, renders a disabled state with an "Upgrade" prompt instead of the child content.
- Used on: "Create Rule" button (destination limit), Risk Overrides section, Symbol Mapping section.

### Telegram Connection State Machine
The Telegram connection page follows a clear state machine:
```
Disconnected → Entering Phone → Code Sent → Entering Code → [2FA Prompt] → Connected
```
Each state renders a different form section. Errors (wrong code, flood wait) show inline.

### Optimistic Rule Toggle
Toggling a routing rule's `is_active` switch:
1. Immediately flips the UI toggle.
2. Sends PATCH to backend.
3. On failure, reverts the toggle and shows a toast error.

## 8. Error Handling

| Error Type | Handling |
|-----------|----------|
| **401 Unauthorized** | Redirect to `/login`, clear JWT from `localStorage` |
| **403 Tier Limit** | Show upgrade modal with tier comparison |
| **404 Not Found** | Show `<NotFound>` component |
| **422 Validation** | Map field errors to React Hook Form `setError` |
| **500 Server Error** | Show generic toast: "Something went wrong. Please try again." |
| **Network Error** | Show toast: "Cannot reach server. Check your connection." |

A top-level `<ErrorBoundary>` catches uncaught rendering errors and displays a fallback UI.

## 9. Testing Strategy

| Layer | Tool | What to Test |
|-------|------|-------------|
| **Unit** | Vitest | Utility functions (`lib/api.ts`, Zod schemas, formatters) |
| **Component** | Vitest + React Testing Library | Forms render correctly, validation fires, tables display data |
| **Integration** | Playwright | Full user flows: login → connect Telegram → create rule → view logs |
| **Accessibility** | axe-core (via Playwright) | All pages pass WCAG 2.1 AA |

### Test file convention:
- Unit/component tests: colocated as `*.test.tsx` next to the source file.
- E2E tests: `frontend/e2e/*.spec.ts`.

## 10. Build & Deployment

```bash
# Development
cd frontend
npm install
npm run dev        # → http://localhost:5173, API requests proxied to localhost:8000

# Production build
npm run build      # Output: frontend/dist/
npm run preview    # Preview the production build locally

# Docker (optional, for docker-compose integration)
docker build -t sgm-frontend ./frontend
```

The production build outputs static files to `dist/`. These can be served by any static file server (Nginx, Caddy, Vercel, Netlify, etc.). Since the app is a pure SPA, the server must be configured to serve `index.html` for all routes (SPA fallback).

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_URL` | `http://localhost:8000` | Backend API base URL |
| `VITE_APP_NAME` | `Signal Copier` | Displayed in header/title |

> **Note**: Vite exposes env vars prefixed with `VITE_` to client code via `import.meta.env.VITE_*`.
