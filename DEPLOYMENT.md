# Deployment Guide

This document outlines how to deploy the KSPDB Fault Localization system from scratch.

## Prerequisites

- **Docker** (v24.0+)
- **Docker Compose** (v2.20+)
- **Git**

## Quick Start (Local)

Run the entire stack via Docker Compose:

```bash
git clone <repo-url>
cd <repo-directory>
docker compose up --build
```

### Verification
1. Open `http://localhost:5173`. You should see the Operator Console.
2. The Active Tickets column should say "No active faults. All clear."
3. Click "Inject DT-001 Fault" in the simulator panel. Within ~3 seconds (skipping the 3-minute debounce in sim-mode), a ticket should appear.

## Environment Variables

A `.env.example` is committed to the repo, though for local testing `docker-compose.yml` provides safe defaults.

| Variable | Description | Required | Safe Default |
| :--- | :--- | :--- | :--- |
| `DATABASE_URL` | PostgreSQL connection string | Yes | `postgresql://user:password@db:5432/fault_localization` |
| `REDIS_URL` | Redis connection string | Yes | `redis://redis:6379/0` |
| `VITE_API_URL` | Backend URL for the React UI | Yes | `http://localhost:8000` |
| `API_URL` | Backend URL for the Simulator | Yes | `http://backend:8000` |

## Troubleshooting Log

Here are the actual failure modes hit while building and deploying this stack:

### 1. Vite WebSocket Connection Refused (CORS / HMR)
**Symptom**: The React app loads, but the browser console is filled with `WebSocket connection to 'ws://localhost:5173/' failed` errors.
**Fix**: Vite's HMR binds to `localhost` inside the container by default. The `frontend/Dockerfile` must expose the host explicitly via `CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]`.

### 2. Database Racing the Backend on Startup
**Symptom**: The `backend` container crashes immediately with `ConnectionRefusedError: [Errno 111] Connect call failed` to PostgreSQL.
**Fix**: While `depends_on` ensures Docker starts the DB container first, Postgres takes several seconds to initialize its internal schemas. Added a `seed_database()` retry loop in the Simulator and robust connection handling in the backend to wait for Postgres to become fully available.

### 3. Out-Of-Order Telemetry Falsely Triggering Restoration
**Symptom**: A ticket was auto-verifying (closing) immediately after creation because an old, delayed heartbeat packet arrived with `energized: true`.
**Fix**: Implemented strict sequence (`seq`) checking in Redis via `ingest.py`. If `payload.seq < last_seq`, the packet is completely discarded.

## Resetting to a Clean State

To wipe the database, clear Redis, and restart from a fresh seed:

```bash
docker compose down -v
docker compose up --build
```
*(The `-v` flag deletes the named volumes attached to the DB and Redis).*
