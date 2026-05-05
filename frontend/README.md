# Cortex Frontend

React 18 + Vite + TypeScript frontend for the Cortex EN 50128 Railway Safety Compliance Platform.

## Dev Setup

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173)

The Vite dev server proxies all `/api/*` requests to `http://localhost:8080` (the Cortex backend).

## Production Build

```bash
npm run build
```

Output goes to `frontend/dist/`.

## Pages

| Page | Route | Description |
|------|-------|-------------|
| Login | `/login` | JWT login with httpOnly cookie |
| Dashboard | `/` | Overview stats, quick search, system health |
| Requirements | `/requirements` | EN 50128 software requirements management |
| SOUPs | `/soups` | SOUP register with approval workflow |
| Assets | `/assets` | Railway infrastructure asset hierarchy |
| RTM | `/rtm` | Requirements Traceability Matrix viewer |
| Test Records | `/test-records` | EN 50128 Table A.3 verification records |
| Audit Log | `/audit` | Immutable, sortable audit trail |
| Agent Chat | `/chat` | AI assistant for requirements analysis |

## API Proxy

Configured in `vite.config.ts`:

```typescript
server: {
  proxy: {
    '/api': 'http://localhost:8080',
  }
}
```
