import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import get_db
from redis_client import get_redis
from topology import topology_manager

router = APIRouter(prefix="/tickets")


class TicketAction(BaseModel):
    action: str   # acknowledge | assign | resolve | close
    notes: str = None


@router.get("/")
async def list_tickets():
    """Returns all tickets, enriched with pole coordinates and confidence rationale.
    Sorted: active faults first (by impact desc), then verified/closed."""
    async for conn in get_db():
        rows = await conn.fetch("""
            SELECT
                t.id, t.dt_id, t.status, t.fault_boundary, t.confidence,
                t.affected_poles_count, t.is_geometric_inference,
                t.created_at, t.resolved_at,
                p_dark.lat      AS fault_lat,
                p_dark.lon      AS fault_lon,
                p_dark.pincode  AS fault_pincode,
                p_live.lat      AS last_live_lat,
                p_live.lon      AS last_live_lon,
                d.lat           AS dt_lat,
                d.lon           AS dt_lon,
                d.feeder_id
            FROM ticket t
            LEFT JOIN pole p_dark ON p_dark.pole_id = (t.fault_boundary->>'first_dark')
            LEFT JOIN pole p_live ON p_live.pole_id = (t.fault_boundary->>'last_live')
            JOIN  dt d ON d.dt_id = t.dt_id
            ORDER BY
                CASE WHEN t.status NOT IN ('verified', 'closed') THEN 0 ELSE 1 END,
                t.affected_poles_count DESC NULLS LAST,
                t.created_at DESC
        """)

        result = []
        for r in rows:
            row = dict(r)
            # Derive a human-readable confidence rationale from existing fields —
            # no new DB column needed.
            if row["is_geometric_inference"]:
                row["confidence_reason"] = (
                    "Topology inferred geometrically (MST) — no recorded wiring for this DT. "
                    "Fault boundary is approximate; real span may differ by one or two poles."
                )
            elif row["confidence"] == "High":
                row["confidence_reason"] = (
                    "Both boundary poles are reporting and recorded wiring topology is used. "
                    "Location is precise to this span."
                )
            else:
                row["confidence_reason"] = (
                    "Partial sensor coverage — some poles have no device or did not report. "
                    "Boundary may be wider than the actual fault."
                )
            result.append(row)
        return result


@router.post("/{ticket_id}/action")
async def ticket_action(ticket_id: int, payload: TicketAction):
    async for conn in get_db():
        ticket = await conn.fetchrow(
            "SELECT * FROM ticket WHERE id = $1", ticket_id
        )
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        current_status = ticket["status"]
        new_status = current_status

        # ── Forward transitions ─────────────────────────────────────
        if payload.action == "acknowledge" and current_status == "detected":
            new_status = "acknowledged"

        elif payload.action == "assign" and current_status in ("detected", "acknowledged"):
            new_status = "assigned"

        elif payload.action == "resolve" and current_status == "assigned":
            # Brief requirement: if lineman marks fixed but poles are still dark,
            # the system must reject it — check Redis right now.
            boundary = ticket["fault_boundary"]
            if isinstance(boundary, str):
                boundary = json.loads(boundary)

            first_dark_id = boundary.get("first_dark")
            pole_still_dark = True  # pessimistic default

            if first_dark_id and first_dark_id != ticket["dt_id"]:
                tree = topology_manager.get_dt_tree(ticket["dt_id"])
                if tree and first_dark_id in tree.nodes:
                    device_id = tree.nodes[first_dark_id].get("device_id")
                    if device_id:
                        redis = get_redis()
                        energized = await redis.hget(
                            f"device:{device_id}", "energized"
                        )
                        pole_still_dark = energized != "1"
            else:
                # DT-level fault — check if any pole is now live
                tree = topology_manager.get_dt_tree(ticket["dt_id"])
                if tree:
                    redis = get_redis()
                    for node in list(tree.nodes):
                        if node == ticket["dt_id"]:
                            continue
                        dev_id = tree.nodes[node].get("device_id")
                        if dev_id:
                            energized = await redis.hget(
                                f"device:{dev_id}", "energized"
                            )
                            if energized == "1":
                                pole_still_dark = False
                                break

            if pole_still_dark:
                return {
                    "status": "error",
                    "message": (
                        "Poles are still reporting dark. "
                        "Restoration must be confirmed by live telemetry — "
                        "the system will auto-verify within seconds of power returning. "
                        "Do not mark resolved until the lights are back on."
                    ),
                }
            new_status = "resolved"

        elif payload.action == "close" and current_status == "verified":
            new_status = "closed"

        else:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot {payload.action!r} a ticket in {current_status!r} status.",
            )

        # ── Persist ─────────────────────────────────────────────────
        if new_status != current_status:
            await conn.execute(
                "UPDATE ticket SET status = $1 WHERE id = $2", new_status, ticket_id
            )

        return {"status": "success", "new_status": new_status}
