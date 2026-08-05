import logging
import json
import networkx as nx
from redis_client import get_redis
from database import get_db
from topology import topology_manager

logger = logging.getLogger(__name__)

async def get_pole_states(dt_id: str, tree: nx.DiGraph):
    redis = get_redis()
    states = {}
    for node in tree.nodes:
        if node == dt_id:
            states[node] = 'LIVE' # DT is assumed live until proven otherwise
            continue
        
        device_id = tree.nodes[node].get('device_id')
        has_device = tree.nodes[node].get('has_device', True)
        
        if not has_device or not device_id:
            states[node] = 'UNKNOWN'
            continue
            
        state_str = await redis.hget(f"device:{device_id}", "energized")
        if state_str == "1":
            states[node] = 'LIVE'
        elif state_str == "0":
            states[node] = 'DARK'
        else:
            states[node] = 'UNKNOWN'
            
    return states

def has_live_descendants(tree: nx.DiGraph, node: str, states: dict):
    # Check if this node has any live descendant
    descendants = nx.descendants(tree, node)
    for d in descendants:
        if states.get(d) == 'LIVE':
            return True
    return False

def count_affected_poles(tree: nx.DiGraph, node: str):
    return len(nx.descendants(tree, node)) + 1 # +1 for the node itself

async def check_scheduled_outage(dt_id: str):
    # Check the Redis flag set by POST /debug/scheduled_outage/{dt_id}
    redis = get_redis()
    flag = await redis.get(f"scheduled_outage:{dt_id}")
    return flag is not None

async def create_or_update_ticket(dt_id: str, fault_boundary: dict, affected_count: int, is_geometric: bool):
    # We serialize the fault boundary to match existing tickets
    boundary_json = json.dumps(fault_boundary)
    
    async for conn in get_db():
        # Check if an active ticket exists for this boundary
        # A simple check: same dt_id and status not in (resolved, verified, closed)
        existing = await conn.fetchrow("""
            SELECT id FROM ticket 
            WHERE dt_id = $1 AND fault_boundary::text = $2
              AND status NOT IN ('verified', 'closed', 'resolved')
        """, dt_id, boundary_json)
        
        if existing:
            logger.info(f"Ticket already exists for boundary {boundary_json}")
            pass
        else:
            logger.info(f"Creating new ticket for boundary {boundary_json}")
            await conn.execute("""
                INSERT INTO ticket (dt_id, fault_boundary, affected_poles_count, is_geometric_inference, confidence)
                VALUES ($1, $2::jsonb, $3, $4, $5)
            """, dt_id, boundary_json, affected_count, is_geometric, "High" if not is_geometric else "Medium")
            
async def verify_restoration(dt_id: str, tree: nx.DiGraph, states: dict):
    # Auto-close tickets if the bounded poles are LIVE again
    async for conn in get_db():
        tickets = await conn.fetch("SELECT id, fault_boundary FROM ticket WHERE dt_id = $1 AND status NOT IN ('verified', 'closed')", dt_id)
        for ticket in tickets:
            boundary = json.loads(ticket['fault_boundary'])
            dark_node = boundary.get("first_dark")
            if dark_node and states.get(dark_node) == 'LIVE':
                # The node that was dark is now live! Auto-verify.
                logger.info(f"Auto-verifying ticket {ticket['id']} due to power restoration.")
                await conn.execute("UPDATE ticket SET status = 'verified', resolved_at = CURRENT_TIMESTAMP WHERE id = $1", ticket['id'])

async def evaluate_dt(dt_id: str):
    logger.info(f"Evaluating faults for DT {dt_id}")
    
    # 1. Scheduled outage check
    if await check_scheduled_outage(dt_id):
        logger.info(f"Scheduled outage active for DT {dt_id}, ignoring faults.")
        return

    tree = topology_manager.get_dt_tree(dt_id)
    if not tree:
        logger.error(f"No topology tree found for DT {dt_id}")
        return
        
    is_geometric = tree.graph.get('is_geometric', False)

    states = await get_pole_states(dt_id, tree)
    
    # 2. Check for restoration
    await verify_restoration(dt_id, tree, states)
    
    # 3. Find faults
    boundaries = []
    
    # Check for DT-level fault: Are ALL poles with known state dark?
    known_poles = [n for n, s in states.items() if s != 'UNKNOWN' and n != dt_id]
    if known_poles and all(states[n] == 'DARK' for n in known_poles):
        logger.warning(f"DT {dt_id} has all known poles dark! DT fault.")
        boundaries.append({
            "type": "DT_FAULT",
            "dt_id": dt_id,
            "last_live": "Substation",
            "first_dark": dt_id,
            "affected": len(known_poles)
        })
        await create_or_update_ticket(dt_id, boundaries[0], len(known_poles), is_geometric)
        return

    # Normal traversal
    def traverse(node, last_live):
        state = states.get(node, 'UNKNOWN')
        
        if state == 'LIVE':
            # Continue down with this as the new last_live
            for child in tree.successors(node):
                traverse(child, node)
        elif state == 'UNKNOWN':
            # Continue down without updating last_live
            for child in tree.successors(node):
                traverse(child, last_live)
        elif state == 'DARK':
            # Check for dead sensor
            if has_live_descendants(tree, node, states):
                logger.info(f"Sensor anomaly detected at {node} (it is DARK but has LIVE descendants). Ignoring.")
                # We ignore this dark state and continue as if UNKNOWN or LIVE
                for child in tree.successors(node):
                    traverse(child, last_live)
            else:
                # Genuine fault boundary
                fault_boundary = {
                    "type": "SPAN_FAULT",
                    "last_live": last_live,
                    "first_dark": node,
                }
                boundaries.append((fault_boundary, count_affected_poles(tree, node)))
                # Do NOT recurse to children; they are dark due to this fault
                
    # Start traversal from children of DT
    for child in tree.successors(dt_id):
        traverse(child, dt_id)
        
    for boundary, affected in boundaries:
        await create_or_update_ticket(dt_id, boundary, affected, is_geometric)
