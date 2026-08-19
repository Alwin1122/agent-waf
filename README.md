# Agent WAF

A security gateway that sits between an AI agent and the tools it is allowed to
call. Every tool invocation passes through this service so that policies such as
rate limiting, parameter validation, data scope and call-sequence enforcement can
be evaluated before a tool ever runs.

**This repository currently contains Phases 1 through 8:** the API foundation,
tool gateway, WAF rule engine, PostgreSQL audit history, Redis runtime state, a
sample OpenAI shopping agent, enforce/shadow policy modes, and a Next.js
operations dashboard, all packaged as a Docker Compose stack. No cloud
deployment or authentication is implemented yet.

**Phase 9A deployment preparation is complete:** the backend container now has
ECS-compatible port, health, readiness, CORS, logging, and shutdown behavior.

## Architecture

The target architecture is:

```
User -> LLM -> AI Agent -> Agent WAF -> Tool Gateway -> Protected Tools
```

The WAF is deliberately independent of tool implementations: it receives a
described tool call, decides, and never imports tool code.

The backend remains a single FastAPI application, with the dashboard packaged
separately:

| Layer | Location | Responsibility |
| --- | --- | --- |
| Entrypoint | `backend/app/main.py` | Builds the app, wires routers and handlers |
| Configuration | `backend/app/config.py` | Environment-driven settings |
| Logging | `backend/app/logging_config.py` | Uniform log format for app and Uvicorn |
| API | `backend/app/api/routes/` | Health probes, tool discovery and tool call ingress |
| Schemas | `backend/app/schemas/` | Pydantic request/response models |
| Core | `backend/app/core/` | Global exception handling |
| Database | `backend/app/db/` | SQLAlchemy models, sessions and repositories |
| Services | `backend/app/services/` | Protected execution and OpenAI orchestration |
| Tools | `backend/app/tools/` | Tool interface, registry and the mock tools |
| Rules | `backend/app/rules/` | WAF engine, four rules and Redis adapters |
| Dashboard | `frontend/` | Next.js UI backed only by audit and metrics APIs |

A tool call flows in one direction with no shortcuts:

```
POST /api/v1/tool-calls -> WAFRuleEngine -> ToolGateway -> ToolRegistry -> Tool
POST /api/v1/agent/chat -> OpenAI -> ProtectedToolService -> WAFRuleEngine
                        -> ToolGateway -> Tool -> OpenAI
```

The WAF evaluates parameter safety, PostgreSQL-backed data scope, required
sequence and rate limits before the route invokes the gateway. A blocking
decision returns HTTP 403 and the tool is not executed. Redis holds rate-limit
counters, successful session history, and idempotency keys. PostgreSQL holds
agents, registered tools, policies and audit logs. In-memory adapters remain
available for isolated tests. Routes never touch the registry or a tool
directly, and tools know nothing about HTTP. The OpenAI service only receives
the `ProtectedToolCaller` interface, so it has no direct ToolGateway execution
path.

## Requirements

- Python 3.12 or newer
- Node.js 18.18 or newer
- Docker and Docker Compose (only for containerised runs)

## Local setup

```bash
cd agent-waf
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
```

## Environment configuration

Copy the example file and adjust as needed. All variables have development
defaults, so a missing `.env` is fine locally.

```bash
cp .env.example .env             # Windows: copy .env.example .env
```

| Variable | Default | Description |
| --- | --- | --- |
| `APP_NAME` | `Agent WAF` | Service name shown in OpenAPI |
| `APP_ENV` | `development` | `development`, `staging` or `production` |
| `LOG_LEVEL` | `INFO` | Standard Python log level |
| `API_PREFIX` | `/api/v1` | Prefix applied to all routes |
| `HOST` | `0.0.0.0` | Backend listener interface |
| `PORT` | `8000` | Backend container port; ECS may override it |
| `CORS_ALLOWED_ORIGINS` | none | Comma-separated deployed frontend origins |
| `CORS_ALLOW_CREDENTIALS` | `false` | Permit credentialed cross-origin requests |
| `PERSISTENCE_ENABLED` | `false` | Use PostgreSQL and Redis adapters |
| `DATABASE_URL` | none | SQLAlchemy PostgreSQL URL; required with persistence |
| `DATABASE_ECHO` | `false` | Emit SQLAlchemy SQL logs |
| `DATABASE_POOL_SIZE` | `5` | SQLAlchemy connection pool size |
| `DATABASE_CONNECT_TIMEOUT_SECONDS` | `5` | PostgreSQL connection timeout |
| `DATABASE_CREATE_TABLES` | `true` | Create the Phase 4 schema at startup |
| `REDIS_URL` | none | Redis connection URL; required with persistence |
| `REDIS_KEY_PREFIX` | `agent-waf` | Namespace applied to every Redis key |
| `REDIS_SOCKET_TIMEOUT_SECONDS` | `5` | Redis connection/operation timeout |
| `REDIS_STATE_TTL_SECONDS` | `86400` | Retention for rate and sequence state |
| `IDEMPOTENCY_TTL_SECONDS` | `3600` | Retention for idempotency keys |
| `IDEMPOTENCY_WAIT_TIMEOUT_SECONDS` | `30` | Maximum wait for a matching in-flight request |
| `OPENAI_API_KEY` | none | Required only for the sample agent endpoint |
| `OPENAI_MODEL` | `gpt-4.1-mini` | OpenAI chat model used by the sample agent |
| `OPENAI_TIMEOUT_SECONDS` | `30` | OpenAI request timeout |
| `WAF_ENFORCEMENT_MODE` | `ENFORCE` | `ENFORCE` blocks; `SHADOW` logs and continues |

Connection URLs can contain credentials and must not be committed. The example
file intentionally leaves all passwords and URLs blank.

## Running locally

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Interactive docs: <http://localhost:8000/docs>

## Running with Docker

Set strong local-only passwords in `.env`:

```dotenv
POSTGRES_PASSWORD=<choose-a-password>
REDIS_PASSWORD=<choose-a-password>
```

Optionally set `OPENAI_API_KEY` in the same file. Then start the frontend,
backend, PostgreSQL and Redis together:

```bash
docker compose up --build
docker compose down
```

Open the dashboard at <http://localhost:3000> and API docs at
<http://localhost:8000/docs>. Compose waits for PostgreSQL and Redis before
starting the backend, then waits for the backend before starting the frontend.
PostgreSQL and Redis use named volumes. Inside the Compose network the backend
connects to hosts `postgres` and `redis`; the frontend proxy connects to
`http://backend:8000`. No container uses host `localhost` for service-to-service
traffic.

## ECS Fargate runtime readiness

The backend image is ready for a future ECS task definition but is not deployed
by this repository. Its container command uses `exec`, listens on `HOST` and
`PORT`, and forwards SIGTERM directly to Uvicorn. The FastAPI lifespan closes
Redis and SQLAlchemy resources before the process exits.

Use `/api/v1/health` as the Application Load Balancer liveness path.
`/api/v1/ready` performs live PostgreSQL and Redis checks and returns HTTP 503
when either dependency is unavailable. Set `CORS_ALLOWED_ORIGINS` to the exact
HTTPS origin of the deployed frontend.

The backend image contains no `.env` file. Inject `DATABASE_URL`, `REDIS_URL`,
`OPENAI_API_KEY`, passwords, and other settings through the ECS task
environment or AWS Secrets Manager when deployment is added. Do not bake
secrets into either image.

## Running the dashboard

The dashboard uses a same-origin Next.js server proxy so the browser does not
need backend CORS access. `BACKEND_API_URL` is read at runtime and defaults to
`http://127.0.0.1:8000`; Compose sets it to `http://backend:8000`.

```bash
cd frontend
npm install
copy .env.example .env.local      # macOS/Linux: cp .env.example .env.local
npm run dev
```

Open <http://localhost:3000>. Summary metrics, recent audit events, and rule
activity refresh every two seconds. The UI preserves the last successful
response if a later refresh fails.

## Running tests

From the repository root:

```bash
pytest
cd frontend
npm run lint
npm run typecheck
npm run build
```

## Endpoints

Paths below assume the default `API_PREFIX` of `/api/v1`.

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/v1/health` | Liveness probe -> `{"status": "healthy"}` |
| GET | `/api/v1/ready` | Readiness probe -> `{"status": "ready"}` |
| GET | `/api/v1/tools` | List registered tools and their parameter schemas |
| GET | `/api/v1/audit` | Paginated WAF audit history |
| GET | `/api/v1/metrics` | Aggregate ALLOW/BLOCK/WOULD_BLOCK counts |
| POST | `/api/v1/tool-calls` | Execute a registered tool through the gateway |
| POST | `/api/v1/agent/chat` | Chat with the OpenAI-powered shopping agent |

## Enforcement and audit history

`WAF_ENFORCEMENT_MODE=ENFORCE` returns HTTP 403 for a policy violation, or HTTP
429 for a rate-limit violation, and never calls ToolGateway.
`WAF_ENFORCEMENT_MODE=SHADOW` records `WOULD_BLOCK`, then continues through
ToolGateway. This applies equally to direct tool calls and OpenAI-generated calls
because both use `ProtectedToolService`.

Every intercepted call records a generated request id, agent/session/tool
identifiers, sanitized parameters, each evaluated rule, effective decision,
reason, mode, timestamp, and WAF/tool latency. Keys containing password, token,
API-key, secret, authorization, credential, or private-key material are masked
before storage. Existing Phase 4 PostgreSQL tables are upgraded idempotently at
startup.

```bash
curl "http://localhost:8000/api/v1/audit?page=1&page_size=20"
curl "http://localhost:8000/api/v1/metrics"
```

## Sample OpenAI agent

Set `OPENAI_API_KEY` in `.env`, start the API, then call:

```bash
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"shopping-agent","session_id":"session-001","message":"Find me a laptop under 60000"}'
```

OpenAI may answer directly or select one of the three registered tools. A model
tool call is converted to the existing `ToolCallRequest` shape and passed to
`ProtectedToolService`; the WAF evaluates it before ToolGateway is reachable.
Blocked calls return HTTP 403 with the blocking rule and reason. The API returns
HTTP 503 when the key is missing and HTTP 502 for provider, malformed model
tool-call, or protected tool execution failures.

## Tools

| Tool | Parameters | Behaviour |
| --- | --- | --- |
| `search_products` | `query`, optional `max_price` | Matches the catalogue on name or category |
| `get_customer` | `customer_id` | Returns a customer, or `customer_not_found` (404) |
| `create_order` | `customer_id`, `product_id`, `quantity` | Creates a mock order with a derived id |

All three are deterministic and backed by a fixed in-memory dataset that is
never mutated, so repeated calls always return the same result.

Example tool call:

```bash
curl -X POST http://localhost:8000/api/v1/tool-calls \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: order-request-001" \
  -d '{"agent_id":"agent-1","session_id":"session-1","tool":"search_products","parameters":{"query":"laptop","max_price":1500}}'
```

When persistence is enabled, `Idempotency-Key` is atomically claimed in Redis.
Replaying the same key and payload returns the stored result without executing
the tool again. Reusing the key with a different payload returns HTTP 409.

Response:

```json
{
  "status": "success",
  "tool": "search_products",
  "result": {
    "query": "laptop",
    "max_price": 1500.0,
    "count": 1,
    "products": [
      {"product_id": "p-1001", "name": "Aurora 14 Laptop", "category": "laptops", "price": 1299.0, "in_stock": true}
    ]
  }
}
```

Unknown fields, empty identifiers and malformed request bodies are rejected
with HTTP 422 and code `validation_error`. An unregistered tool returns HTTP
404 with code `tool_not_found`, and parameters a tool refuses return HTTP 422
with code `tool_input_error`. WAF blocks return HTTP 403, or HTTP 429 for
rate-limit violations, with code `waf_blocked`, the blocking rule, and a
non-sensitive reason.

## Error format

Every failure returns the same envelope; internal errors are logged in full but
returned to the client without stack traces.

```json
{
  "status": "error",
  "code": "validation_error",
  "message": "Request validation failed.",
  "details": [
    {"location": "body.tool", "message": "String should have at least 1 character", "type": "string_too_short"}
  ]
}
```
