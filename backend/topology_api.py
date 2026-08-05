from fastapi import APIRouter, HTTPException
from topology import topology_manager
from redis_client import get_redis

router = APIRouter(prefix="/topology")


@router.get("/")
async def list_dts():
    """Lightweight: all DT positions + pole count for the map overview."""
    result = []
    for dt_id, tree in topology_manager.dt_trees.items():
        dt_data = tree.nodes[dt_id]
        result.append(
            {
                "dt_id": dt_id,
                "lat": dt_data.get("lat"),
                "lon": dt_data.get("lon"),
                "pole_count": tree.number_of_nodes() - 1,
                "is_geometric": tree.graph.get("is_geometric", False),
            }
        )
    return result


@router.get("/{dt_id}")
async def get_dt_topology(dt_id: str):
    """Full topology for one DT: every node with its current energised state from Redis."""
    tree = topology_manager.get_dt_tree(dt_id)
    if not tree:
        raise HTTPException(status_code=404, detail=f"DT '{dt_id}' not found in topology.")

    redis = get_redis()
    nodes = []

    for node, data in tree.nodes(data=True):
        if node == dt_id:
            state = "LIVE"
        else:
            device_id = data.get("device_id")
            if device_id:
                energized = await redis.hget(f"device:{device_id}", "energized")
                if energized == "1":
                    state = "LIVE"
                elif energized == "0":
                    state = "DARK"
                else:
                    state = "UNKNOWN"
            else:
                state = "NO_DEVICE"

        nodes.append(
            {
                "id": node,
                "type": data.get("type", "pole"),
                "lat": data.get("lat"),
                "lon": data.get("lon"),
                "state": state,
                "has_device": data.get("has_device", False),
            }
        )

    edges = [{"from": u, "to": v} for u, v in tree.edges()]

    return {
        "dt_id": dt_id,
        "is_geometric": tree.graph.get("is_geometric", False),
        "nodes": nodes,
        "edges": edges,
    }
