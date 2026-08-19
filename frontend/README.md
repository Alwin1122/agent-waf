# Agent WAF Dashboard

Next.js, TypeScript and Tailwind CSS dashboard for the Agent WAF audit and
metrics APIs.

## Local development

```bash
npm install
copy .env.example .env.local
npm run dev
```

Open <http://localhost:3000>. `BACKEND_API_URL` defaults to
`http://127.0.0.1:8000`. The browser calls a same-origin Next.js proxy, so the
backend does not need CORS configuration.

## Checks

```bash
npm run lint
npm run typecheck
npm run build
```

## Docker

The multi-stage image produces a non-root Next.js standalone server on port
3000. From the repository root:

```bash
docker compose up --build
```

Compose sets `BACKEND_API_URL=http://backend:8000`, using the backend service
name rather than localhost.
