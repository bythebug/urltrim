# urltrim

Tiny personal URL shortener – short links, redirects, click counts, rate limiting, and custom aliases.  
Stack: **FastAPI + PostgreSQL + Redis + RabbitMQ**.

---

## Architecture (high level)

```text
[Client / Browser]
    ├─ POST /shorten ───────────────▶ [FastAPI API]
    ├─ GET /<code> (redirect) ─────▶ [FastAPI API]
    └─ GET /analytics/<code> ──────▶ [FastAPI API]

[FastAPI API]
    ├─ read/write link metadata ───▶ [PostgreSQL]
    ├─ cache + rate limiting ──────▶ [Redis]
    └─ publish click events ───────▶ [RabbitMQ]

[RabbitMQ]
    └─ deliver click messages ─────▶ [Click worker (consumer.py)]

[Click worker]
    └─ increment click counters ───▶ [PostgreSQL]
```

### Redirect path (hot path)

- `GET /{code}` checks Redis first (`url:{code}`), falls back to Postgres, then caches the result in Redis.
- A click event is published to RabbitMQ on every redirect; the worker increments `links.clicks` asynchronously.

---

## Scaling strategy (what I’d do in production)

- **API (FastAPI)**: keep it stateless so it can scale horizontally behind a load balancer.
- **Redirect caching**:
  - Redis becomes the “read-mostly” layer for `code -> long_url`.
  - Increase TTL / add cache warming for popular links.
  - Consider local in-process cache (tiny TTL) if Redis roundtrips become the bottleneck.
- **Rate limiting**:
  - Currently per-IP; in production you’d likely key by API key / user ID and/or use a reverse proxy (Nginx/Envoy) for first-pass limiting.
- **Postgres**:
  - Primary + read replicas for analytics reads if needed.
  - Add a separate analytics table if `links` becomes write-hot.
  - Partition click aggregation if you move beyond a simple counter.
- **RabbitMQ / workers**:
  - Add more consumers for higher click throughput.
  - Prefer idempotent increments (or aggregate in Redis then flush) if “exactly once” matters.

---

## Tradeoffs (intentional)

- **Analytics is eventually consistent**: redirects publish events; the worker updates Postgres. If the worker lags, `/analytics/{code}` trails reality.
- **At-least-once delivery**: the consumer can requeue on failures → clicks can overcount in rare retry scenarios.
- **Schema management**: the app uses `create_all()` on startup (fast for a personal project). For “real” deploys, I’d switch to Alembic migrations.
- **Rate limiting behavior**: `/shorten` returns `429` under load by design; redirects are not rate-limited.
- **Publisher implementation**: click publishing uses a thread executor to avoid blocking the event loop (simple, but not the most efficient approach at very high QPS).

---

## Run locally (no Docker)

### 1. Env + dependencies

```bash
cd urltrim

cp .env.example .env          # tweak if you want

python -m venv .venv
source .venv/bin/activate     # or .venv\Scripts\activate on Windows

pip install -r requirements.txt
```

You need Postgres, Redis, and RabbitMQ running on localhost.
On macOS with Homebrew:

```bash
brew services start postgresql@16
brew services start redis
brew services start rabbitmq
```

If you’re not using those defaults, adjust `DATABASE_URL`, `REDIS_URL`, `RABBITMQ_URL` in `.env`.

### 2. API + click worker

```bash
# terminal 1 – API
source .venv/bin/activate
uvicorn main:app --reload --port 8001

# terminal 2 – analytics worker
source .venv/bin/activate
python -m consumer
```

- API: `http://localhost:8001`  
- Docs: `http://localhost:8001/docs`

---

## Run with Docker (services or full stack)

This repo includes a small `docker-compose.yml` so you don’t have to install Postgres/Redis/RabbitMQ manually.

### Option A – only infra in Docker (app on host)

```bash
# start Postgres, Redis, RabbitMQ in containers
docker-compose up -d postgres redis rabbitmq

# then, on host:
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

uvicorn main:app --reload --port 8001        # terminal 1
python -m consumer                           # terminal 2
```

This matches the defaults in `.env.example` (they point to `localhost`).

### Option B – run API in Docker too

```bash
# build image
docker build -t urltrim-api .

# start infra + api container
docker-compose up -d
```

When running inside Docker, point the app at the compose service names. For example:

```bash
docker run --rm -p 8001:8000 \
  -e DATABASE_URL=postgresql+asyncpg://urltrim:urltrim@postgres:5432/urltrim \
  -e REDIS_URL=redis://redis:6379/0 \
  -e RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/ \
  urltrim-api
```

Then hit `http://localhost:8001`.

---

## Deploy (practical options)

### Single VM (Docker Compose)

- Put this repo on a VM.
- Run `docker-compose up -d` for infra.
- Run the API container and a separate worker process/container (recommended to keep them independently scalable).
- Use a reverse proxy (Caddy/Nginx) for TLS and to set sane timeouts.

### Kubernetes (sketch)

- Deploy **API** as a `Deployment` (HPA on CPU/RPS).
- Deploy **worker** as a separate `Deployment` (HPA on queue depth).
- Use managed Postgres/Redis/RabbitMQ where possible.
- Configure health checks:
  - API: `GET /`
  - Worker: liveness via process health + RabbitMQ connectivity.

---

## API surface

- **Shorten**
  - **Endpoint**: `POST /shorten`
  - **Body**: `{"url": "https://...", "alias": "optional-custom-code"}`
  - **Behavior**:
    - No `alias` → random short code (e.g. `xgrn2c`)
    - `alias: "string"` or `""` (Swagger default) → treated as no alias (random)
    - Any other alias → used as the exact path segment (must be unique)

- **Redirect**
  - **Endpoint**: `GET /{code}`
  - 302 redirect to original URL
  - Uses Redis as a cache for `code → long_url`

- **Analytics**
  - **Endpoint**: `GET /analytics/{code}`
  - Returns `{"short_code": "...", "clicks": N}`
  - Clicks are updated by the RabbitMQ consumer (`consumer.py`)

- **Rate limiting**
  - 60 requests/min per IP on `POST /shorten` (configurable via `rate_limit_per_minute`)

---

## Load testing (Locust)

```bash
pip install locust
locust -f locustfile.py --host http://localhost:8001
# then open http://localhost:127.0.0.1:8089 and start a run
```

The `UrlTrimUser` scenario:
- Creates a few short URLs on startup
- Hammers redirects more than shortens
- Occasionally hits `/analytics/{code}`

### Load testing results (local run)

**Command**

```bash
locust -f locustfile.py --headless -u 100 -r 10 -t 45s --host http://127.0.0.1:8001
```

**Notes**

- `/shorten` is rate-limited (60/min/IP), so under load most `/shorten` calls intentionally return **429**.
- Redirect and analytics stayed at **0% failures**.

**Snapshot**

- **Total**: 13,480 requests, ~300 req/s aggregated
- **Redirect** (`GET /{code}`): 7,765 requests, ~173 req/s, **p95 ~22ms**
- **Analytics** (`GET /analytics/{code}`): 2,711 requests, ~60 req/s, **p95 ~9ms**
- **Shorten** (`POST /shorten`): 3,004 requests, **2,944 were 429s** (rate limit working as designed)

---

## Files at a glance

- `main.py` – FastAPI app + lifespan (creates tables, cleans up Redis / DB)
- `routes.py` – `/shorten`, `/{code}`, `/analytics/{code}`
- `link_service.py` – create + lookup links, alias validation
- `short_code.py` – random code generator (no ambiguous chars like `0/O` or `1/l/i`)
- `rate_limit.py` – Redis sliding-window rate limiting
- `redis_client.py` – Redis connection pool
- `mq.py` – RabbitMQ publisher for click events
- `consumer.py` – RabbitMQ consumer → increments `links.clicks` in Postgres
- `db.py`, `models.py` – async SQLAlchemy + `Link` model
- `config.py` – settings via `pydantic-settings`
- `locustfile.py` – simple load test profile

---

## PostgreSQL schema

The app will create tables automatically on startup, but if you want to see or manage the schema explicitly, here’s the minimal structure:

```sql
CREATE TABLE links (
  id          SERIAL PRIMARY KEY,
  long_url    VARCHAR(2048) NOT NULL,
  short_code  VARCHAR(64)   NOT NULL UNIQUE,
  alias       VARCHAR(64)   UNIQUE,
  clicks      INTEGER       NOT NULL DEFAULT 0,
  created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_links_short_code ON links (short_code);
```

Semantics:

- `short_code`: the code used in the URL (e.g. `/xgrn2c` or `/my-custom-alias`).
- `alias`: optional alias field (currently mirrors `short_code` when a custom alias is provided).
- `clicks`: total redirects processed (updated by the RabbitMQ consumer).
