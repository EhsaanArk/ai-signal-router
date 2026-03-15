# Frontend Setup Guide

## 1. Prerequisites

- **Node.js** 20 LTS or later
- **npm** 10+ (ships with Node 20)
- Backend API running on `http://localhost:8000` (see root `docker-compose.yml`)

## 2. Bootstrap the Project

```bash
# From the project root
npm create vite@latest frontend -- --template react-ts

cd frontend
```

## 3. Install Dependencies

### Core
```bash
npm install react-router-dom @tanstack/react-query@5 react-hook-form @hookform/resolvers zod lucide-react
```

### Tailwind CSS 4 (Vite plugin)
```bash
npm install -D tailwindcss @tailwindcss/vite
```

Then add the Tailwind plugin to `vite.config.ts`:
```typescript
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
});
```

### shadcn/ui
```bash
npx shadcn@latest init
# Choose: New York style, Zinc base color, CSS variables = yes

# Install the components needed for V1
npx shadcn@latest add button card badge dialog alert-dialog \
  input label select table tabs toast skeleton \
  dropdown-menu separator sheet form
```

### Dev Dependencies
```bash
npm install -D @testing-library/react @testing-library/jest-dom \
  vitest @vitejs/plugin-react jsdom \
  playwright @playwright/test \
  @axe-core/playwright
```

## 4. Environment Variables

Create `frontend/.env`:

```env
# Backend API URL (FastAPI running via docker-compose)
VITE_API_URL=http://localhost:8000

# App display name
VITE_APP_NAME=Signal Copier
```

Access in code via `import.meta.env.VITE_API_URL`. For production, set `VITE_API_URL` to the deployed Railway backend URL.

> **Note**: Vite only exposes variables prefixed with `VITE_` to the client bundle. Never put secrets in `VITE_` variables.

## 5. Development

```bash
cd frontend

# Start dev server (hot reload on port 5173)
npm run dev

# Run unit/component tests
npm test

# Run e2e tests (requires backend running)
npx playwright test

# Lint
npm run lint

# Type check
npx tsc --noEmit
```

## 6. Project Scripts

Add these to `frontend/package.json`:

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "lint": "eslint .",
    "test": "vitest",
    "test:ui": "vitest --ui",
    "test:e2e": "playwright test",
    "typecheck": "tsc --noEmit"
  }
}
```

## 7. Docker Integration (Optional)

To add the frontend to the existing `docker-compose.yml`:

### `frontend/Dockerfile`
```dockerfile
FROM node:20-alpine AS base

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Development
FROM base AS dev
CMD ["npm", "run", "dev", "--", "--host"]

# Production
FROM base AS builder
RUN npm run build

FROM nginx:alpine AS production
COPY --from=builder /app/dist /usr/share/nginx/html
# SPA fallback: serve index.html for all routes
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### `frontend/nginx.conf` (for production Docker image)
```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

### Add to `docker-compose.yml`
```yaml
  frontend:
    build:
      context: ./frontend
      target: dev
    container_name: sgm-frontend
    ports:
      - "5173:5173"
    environment:
      - VITE_API_URL=http://api:8000
    volumes:
      - ./frontend:/app
      - /app/node_modules
    depends_on:
      - api
```

Then: `docker-compose up --build` starts everything including the frontend at `http://localhost:5173`.

## 8. CORS Configuration

The backend needs to allow requests from the frontend origin. Add to `src/main.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Frontend dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

For production, replace with the actual frontend domain.

## 9. Recommended VS Code Extensions

- **Tailwind CSS IntelliSense** — autocomplete for Tailwind classes
- **ESLint** — inline linting
- **Prettier** — auto-format on save (configure to use Tailwind plugin)
- **TypeScript Error Translator** — human-readable TS errors

## 10. Folder Scaffold Commands

After `npm create vite@latest`, create the directory structure from `FRONTEND_ARCHITECTURE.md`:

```bash
cd frontend/src

# Page components
mkdir -p pages

# Components
mkdir -p components/forms components/tables components/layout components/shared

# Contexts, lib, hooks, types
mkdir -p contexts lib hooks types
```
