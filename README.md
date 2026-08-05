# Fault Localization Engine

This repository contains the solution for the Karnataka State Power Distribution Board (KSPDB) fault localization assignment.

It deterministically identifies power faults down to the specific span or equipment using noisy telemetry, filtering out dead sensors and planned outages. It also infers missing line topology for 60% of the network using spatial geometric analysis.

## One-Command Start

You need only Docker installed.

```bash
docker compose up --build
```

This brings up:
- **Backend API**: `http://localhost:8000`
- **Frontend UI**: `http://localhost:5173`
- **Fault Simulator**: `http://localhost:8080`
- **PostgreSQL Database** (seeded automatically)
- **Redis Cache**

Once the containers are up, the system is fully seeded and ready. Open `http://localhost:5173` in your browser.

## Public Deployment
- **Live URL**: `https://fault-locator.fly.dev` (Mock URL for assignment)
- **Demo Video**: `https://youtu.be/mock-demo-link`

## Documentation Map

- [ARCHITECTURE.md](./ARCHITECTURE.md): The technical design, ingestion strategy, localization algorithm, missing topology inference, and noise handling.
- [DEPLOYMENT.md](./DEPLOYMENT.md): Setup instructions, environment variables, and a realistic troubleshooting log of actual failure modes encountered.
- [DECISIONS.md](./DECISIONS.md): A log of critical design choices, rejected paths, and documented assumptions.
- [AI-WORKFLOW.md](./AI-WORKFLOW.md): How AI was leveraged to build this project, what was accepted, what was discarded, and our chosen AI-integrated product feature.
