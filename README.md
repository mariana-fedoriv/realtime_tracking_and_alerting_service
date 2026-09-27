# Real-Time Geo-Tracking & Alerting Service

Backend service that ingests device coordinates, streams them to connected
web clients, and pushes real-time alerts when a device enters a user-defined
circular geozone.

## Stack

- FastAPI (async) + Uvicorn
- PostgreSQL + PostGIS, via SQLAlchemy 2.0 async + GeoAlchemy2
- Redis (pub/sub fan-out for WebSocket events)
- Alembic migrations
- Docker / docker-compose

## Running it

```bash
docker compose up --build
```

This starts `db` (Postgres+PostGIS), `redis`, runs `migrate` (Alembic
`upgrade head`) once, then starts `app` on http://localhost:8000. Open that
URL for a minimal Leaflet demo page (create geozones, connect a WebSocket
session, watch devices move).

Local (non-Docker) dev:

```bash
uv sync
cp .env.example .env   # point DATABASE_URL/REDIS_URL at local services
alembic upgrade head
uvicorn app.main:app --reload
```

### Auth

There's no real auth. Every request identifies its user via an `X-User-Id`
header (WebSocket connections pass `?user_id=...` as a query param, since
browsers can't set custom headers on the WebSocket handshake). Two different
`X-User-Id` values are two different users with isolated geozones.

## API

- `POST /api/v1/devices/location` — ingest one `{device_id, latitude,
  longitude, timestamp}` reading. Returns `202` immediately; `503` if the
  ingestion queue is saturated (client should back off and retry).
- `POST /api/v1/geozones`, `GET /api/v1/geozones`, `GET /api/v1/geozones/{id}`,
  `PUT /api/v1/geozones/{id}`, `DELETE /api/v1/geozones/{id}` — CRUD, scoped
  to the caller's `X-User-Id`.
- `WS /ws?user_id=...` — live feed. Two message types are pushed:
  - `location_update`: broadcast to every connected client (drives the live
    map).
  - `alert`: sent only to the sessions belonging to the geozone's owner.

## Running the load generator

```bash
python generator.py --devices 10000 --base-url http://localhost:8000 --interval 5 --duration 120
```

Each device is its own asyncio task that drifts its position by a small
random delta every tick and POSTs it. `--concurrency` bounds how many HTTP
requests are in flight at once (shared connection pool), independent of how
many devices are simulated, so you can dial up device count without opening
10k sockets simultaneously. On `503` a device backs off with jittered
exponential retry.

## Running tests

Unit tests (`tests/test_schemas.py`) need nothing running. The geozone
integration tests (`tests/test_geozone_service.py`) need a live PostGIS
instance — they'll `pytest.skip` automatically if one isn't reachable:

```bash
docker compose up -d db   # published on localhost:55432 to avoid clashing with a local Postgres
uv sync --group dev
TEST_DATABASE_URL=postgresql+asyncpg://geo:geo@localhost:55432/geo_tracking uv run pytest
```

## Architecture notes

### Spatial queries

Device locations and geozone centers are stored as PostGIS `Geography(Point,
4326)` columns (not `Geometry`), so distance/containment math accounts for
the Earth's curvature without any manual projection handling, and radii are
expressed directly in meters. Matching a device ping against every user's
geozones is a single indexed query:

```sql
SELECT * FROM geozones WHERE ST_DWithin(center, :point, radius_m)
```

`center` and `point` both being `geography` means `ST_DWithin`'s third
argument is meters, matching `radius_m` with no unit conversion. Both
`locations.point` and `geozones.center` have GIST indexes, so this scales
with the number of geozones instead of doing a sequential scan — all of it
runs in Postgres, never by pulling rows into Python and computing haversine
distance in a loop. See `app/services/geozone_service.py::find_matching_geozones`.

### High-throughput ingestion

`POST /api/v1/devices/location` does no I/O beyond validating the payload
and calling `queue.put_nowait()` on an in-process `asyncio.Queue`, then
returns `202`. A fixed pool of background workers (`INGEST_WORKER_COUNT`,
default 8) drains that queue, each doing one DB write + spatial match + Redis
publish per item. This decouples inbound HTTP concurrency from DB
concurrency: whether 100 or 10,000 devices are POSTing at once, only
`INGEST_WORKER_COUNT` DB operations are ever in flight, which is what keeps
the SQLAlchemy pool (`DB_POOL_SIZE` + `DB_MAX_OVERFLOW`) from being exhausted.
If the queue itself fills up (workers falling behind), new POSTs get a `503`
instead of blocking or growing memory unboundedly — that's the backpressure
signal `generator.py` reacts to.

### WebSocket state management

Each app process keeps an in-memory `ConnectionManager` mapping
`user_id -> set[WebSocket]`, so one user's laptop-and-phone sessions both
live in the same set and both receive everything addressed to that user.
Sending to a user (or broadcasting to everyone, for the live map) fires all
`send_text` calls concurrently via `asyncio.gather`, so one slow client can't
stall delivery to the rest.

Because connection state is local to a process, a second requirement had to
be solved: an alert triggered by ingestion traffic hitting *replica A* must
still reach a user whose WebSocket is connected to *replica B*. Every event
(`location_update` or `alert`) is published to a single Redis pub/sub
channel; every replica subscribes to that channel and, on receipt, only
delivers to the WebSocket connections it physically holds
(`app/services/redis_bus.py`). This keeps the design horizontally scalable
without needing sticky sessions or a shared connection registry.

### Async throughout

FastAPI routes, SQLAlchemy (asyncpg driver), Redis client, and the ingestion
workers are all async, so the event loop is never blocked waiting on I/O.
The one CPU-bound-looking piece — geozone matching — is actually pushed down
into Postgres via `ST_DWithin` rather than computed in Python, so there's no
synchronous spatial computation sitting in the event loop at all.
