import os
import time
import random
import threading
import requests
import psycopg2
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pydantic import BaseModel
from datetime import datetime, timezone

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/fault_localization")
API_URL      = os.getenv("API_URL",      "http://localhost:8000")

app = FastAPI(title="Fault Simulator")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class FaultRequest(BaseModel):
    target_id: str   # DT-id or pole-id depending on fault type

# In-memory state populated on startup
devices      = {}  # device_id -> {seq, fw, pole_id, dt_id}
network_tree = {}  # dt_id    -> [pole_id, ...]
dt_feeder    = {}  # dt_id    -> feeder_id


def seed_database():
    conn = psycopg2.connect(DATABASE_URL)
    cur  = conn.cursor()

    cur.execute("SELECT count(*) FROM dt")
    if cur.fetchone()[0] > 0:
        print("Database already seeded — loading devices.")
        cur.execute("SELECT p.device_id, p.pole_id, p.dt_id, d.feeder_id "
                    "FROM pole p JOIN dt d ON p.dt_id = d.dt_id "
                    "WHERE p.has_device = TRUE")
        for dev, pole, dt, feeder in cur.fetchall():
            fw = "1.2.0" if random.random() < 0.08 else "1.4.2"
            devices[dev] = {"seq": 0, "fw": fw, "pole_id": pole, "dt_id": dt}
            if dt not in network_tree:
                network_tree[dt] = []
            network_tree[dt].append(pole)
            dt_feeder[dt] = feeder
        conn.close()
        return

    print("Seeding database…")
    for dt_num in range(1, 51):
        dt_id    = f"DT-{dt_num:03d}"
        feeder_id = f"F-{dt_num % 5 + 1}"
        dt_lat   = 12.9 + random.uniform(-0.05, 0.05)
        dt_lon   = 77.5 + random.uniform(-0.05, 0.05)

        cur.execute("INSERT INTO dt (dt_id, feeder_id, lat, lon) VALUES (%s, %s, %s, %s)",
                    (dt_id, feeder_id, dt_lat, dt_lon))

        has_wiring  = (dt_num <= 20)   # 40% with known topology
        num_poles   = random.randint(30, 80)
        parent      = None
        network_tree[dt_id] = []
        dt_feeder[dt_id]    = feeder_id

        for p_num in range(1, num_poles + 1):
            pole_id   = f"P-{dt_num:03d}-{p_num:03d}"
            device_id = f"DEV-{pole_id}" if random.random() > 0.09 else None
            pincode   = "560001" if random.random() > 0.03 else None
            p_lat     = dt_lat + (p_num * 0.0001)
            p_lon     = dt_lon + (p_num * 0.0001)
            p_parent  = parent if has_wiring else None
            seq_on    = p_num  if has_wiring else None

            cur.execute("""
                INSERT INTO pole (pole_id, dt_id, parent_pole_id, seq_on_line,
                                  device_id, has_device, lat, lon, pincode)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (pole_id, dt_id, p_parent, seq_on,
                  device_id, device_id is not None, p_lat, p_lon, pincode))

            if device_id:
                fw = "1.2.0" if random.random() < 0.08 else "1.4.2"
                devices[device_id] = {"seq": 0, "fw": fw, "pole_id": pole_id, "dt_id": dt_id}

            network_tree[dt_id].append(pole_id)
            parent = pole_id

    conn.commit()
    conn.close()
    print("Seeding complete.")


def send_telemetry(device_id: str, event: str, energized: bool):
    if device_id not in devices:
        return
    d = devices[device_id]
    d["seq"] += 1

    # 30% message loss on power_lost events
    if event == "power_lost" and random.random() < 0.30:
        return
    # fw 1.2.x doesn't send power_lost
    if event == "power_lost" and d["fw"].startswith("1.2"):
        return

    payload = {
        "device_id": device_id,
        "pole_id":   d["pole_id"],
        "event":     event,
        "energized": energized,
        "ts":        datetime.now(timezone.utc).isoformat(),
        "seq":       d["seq"],
        "battery_mv": 3500 if energized else 2900,
        "rssi":      -85,
        "fw":        d["fw"],
    }
    try:
        requests.post(f"{API_URL}/telemetry", json=payload, timeout=2)
    except Exception as e:
        print(f"Telemetry send failed for {device_id}: {e}")


# ──────────────────────────── Discovery ────────────────────────────

@app.get("/dts")
def list_dts():
    return [
        {"dt_id": dt_id, "feeder_id": dt_feeder.get(dt_id, "?"), "pole_count": len(poles)}
        for dt_id, poles in network_tree.items()
    ]


@app.get("/feeders")
def list_feeders():
    return sorted(set(dt_feeder.values()))


@app.get("/poles/{dt_id}")
def list_poles(dt_id: str):
    return network_tree.get(dt_id, [])


# ──────────────────────────── Fault injection ───────────────────────

@app.post("/inject/dt_fault")
def inject_dt_fault(req: FaultRequest):
    """All devices in a DT go dark — simulates a DT/HT-fuse failure."""
    dt_id = req.target_id
    devs  = [dev for dev, data in devices.items() if data["dt_id"] == dt_id]
    for dev in devs:
        time.sleep(random.uniform(0.001, 0.01))
        send_telemetry(dev, "power_lost", False)
    return {"status": "injected", "dt_id": dt_id, "affected": len(devs)}


@app.post("/inject/span_fault")
def inject_span_fault(req: FaultRequest):
    """A pole and all downstream poles go dark — simulates a line-section fault."""
    pole_id = req.target_id
    dt_id   = next((d["dt_id"] for d in devices.values() if d["pole_id"] == pole_id), None)
    if not dt_id:
        return {"status": "pole_not_found"}

    poles = network_tree[dt_id]
    try:
        idx      = poles.index(pole_id)
        affected = poles[idx:]
        devs     = [dev for dev, data in devices.items() if data["pole_id"] in affected]
        for dev in devs:
            time.sleep(random.uniform(0.001, 0.01))
            send_telemetry(dev, "power_lost", False)
        return {"status": "injected", "first_dark": pole_id, "affected": len(devs)}
    except ValueError:
        return {"status": "pole_not_in_dt_tree"}


@app.post("/inject/feeder_fault")
def inject_feeder_fault(req: FaultRequest):
    """All DTs on a feeder go dark — simulates an upstream feeder trip."""
    feeder_id   = req.target_id
    target_dts  = [dt for dt, fdr in dt_feeder.items() if fdr == feeder_id]
    total = 0
    for dt_id in target_dts:
        devs = [dev for dev, data in devices.items() if data["dt_id"] == dt_id]
        for dev in devs:
            time.sleep(random.uniform(0.001, 0.01))
            send_telemetry(dev, "power_lost", False)
        total += len(devs)
    return {"status": "injected", "feeder": feeder_id, "dts": target_dts, "devices_affected": total}


@app.post("/inject/fast_fault")
def inject_fast_fault(req: FaultRequest, fault_type: str = "span_fault"):
    """Inject a fault and immediately force-evaluate (bypasses 3-min debounce).
    target_id should be a DT-id; the endpoint picks a mid-network pole for span faults."""
    dt_id = req.target_id

    if fault_type == "dt_fault":
        inject_dt_fault(req)
    else:
        poles = network_tree.get(dt_id, [])
        if not poles:
            return {"status": "error", "detail": f"No poles for DT {dt_id}"}
        # Pick ~1/3 into the network for a realistic span fault
        pole_id = poles[max(0, len(poles) // 3)]
        inject_span_fault(FaultRequest(target_id=pole_id))

    time.sleep(0.5)   # let telemetry land in Redis

    try:
        r = requests.post(f"{API_URL}/debug/evaluate/{dt_id}", timeout=10)
        return {"status": "injected_and_evaluated", "dt_id": dt_id, "backend": r.json()}
    except Exception as e:
        return {"status": "injected_no_evaluate", "detail": str(e)}


# ──────────────────────────── Noise cases ──────────────────────────

@app.post("/inject/dead_sensor")
def inject_dead_sensor(req: FaultRequest):
    """Send a dark signal for ONE pole only — its children remain live.
    The localization algorithm must detect 'live descendants' and NOT create a ticket."""
    pole_id = req.target_id
    dev = next((d for d, data in devices.items() if data["pole_id"] == pole_id), None)
    if not dev:
        return {"status": "pole_not_found"}

    d = devices[dev]
    d["seq"] += 1
    payload = {
        "device_id": dev,
        "pole_id":   d["pole_id"],
        "event":     "power_lost",
        "energized": False,
        "ts":        datetime.now(timezone.utc).isoformat(),
        "seq":       d["seq"],
        "battery_mv": 2900,
        "rssi":       -85,
        "fw":         d["fw"],
    }
    try:
        requests.post(f"{API_URL}/telemetry", json=payload, timeout=2)
    except Exception as e:
        return {"status": "error", "detail": str(e)}

    return {
        "status": "injected_dead_sensor",
        "pole":   pole_id,
        "note":   "Only this pole sent dark. Children are still live. No ticket should be raised.",
    }


@app.post("/inject/scheduled_outage")
def inject_scheduled_outage(req: FaultRequest, active: bool = True):
    """Tell the backend to suppress tickets for this DT — simulates a planned outage."""
    try:
        r = requests.post(
            f"{API_URL}/debug/scheduled_outage/{req.target_id}",
            params={"active": str(active).lower()},
            timeout=5,
        )
        return {"status": "ok", "backend_response": r.json()}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# ──────────────────────────── Restoration ──────────────────────────

@app.post("/restore/{dt_id}")
def restore_dt(dt_id: str):
    """Restore all poles in a DT to live — triggers auto-verification of open tickets."""
    devs = [dev for dev, data in devices.items() if data["dt_id"] == dt_id]
    for dev in devs:
        send_telemetry(dev, "power_restored", True)
    return {"status": "restored", "dt_id": dt_id, "count": len(devs)}


# ──────────────────────────── Entry point ──────────────────────────

if __name__ == "__main__":
    while True:
        try:
            seed_database()
            break
        except Exception as e:
            print(f"Waiting for DB… {e}")
            time.sleep(2)

    uvicorn.run(app, host="0.0.0.0", port=8080)
