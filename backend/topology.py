import math
import networkx as nx
import logging

logger = logging.getLogger(__name__)

class TopologyManager:
    def __init__(self):
        self.dt_trees = {} # dt_id -> nx.DiGraph
        self.pole_to_dt = {} # pole_id -> dt_id
        self.pole_metadata = {} # pole_id -> {device_id, lat, lon, etc}

    async def load_from_db(self, pool):
        logger.info("Loading topology from DB...")
        async with pool.acquire() as conn:
            poles = await conn.fetch("SELECT * FROM pole")
            dts = await conn.fetch("SELECT * FROM dt")
        
        # Group poles by DT
        dt_poles = {dt['dt_id']: [] for dt in dts}
        for pole in poles:
            dt_id = pole['dt_id']
            if dt_id in dt_poles:
                dt_poles[dt_id].append(pole)
            self.pole_to_dt[pole['pole_id']] = dt_id
            self.pole_metadata[pole['pole_id']] = dict(pole)
            
        dt_metadata = {dt['dt_id']: dict(dt) for dt in dts}

        for dt_id, p_list in dt_poles.items():
            dt_info = dt_metadata[dt_id]
            # Check if this DT has wiring data
            # If at least one pole has parent_pole_id (and it's not some weird edge case), we assume 40% known.
            # Actually, the spec says for 60%, seq_on_line and parent_pole_id are empty.
            has_wiring = any(p['parent_pole_id'] is not None for p in p_list)
            
            tree = nx.DiGraph()
            # Add root DT node
            tree.add_node(dt_id, type='dt', lat=dt_info['lat'], lon=dt_info['lon'])
            
            for p in p_list:
                tree.add_node(p['pole_id'], type='pole', lat=p['lat'], lon=p['lon'], has_device=p['has_device'], device_id=p['device_id'])
                
            if has_wiring:
                # Build explicit tree
                for p in p_list:
                    parent = p['parent_pole_id']
                    if parent:
                        tree.add_edge(parent, p['pole_id'])
                    else:
                        # Connected directly to DT
                        tree.add_edge(dt_id, p['pole_id'])
            else:
                # 60% missing topology: Build MST
                # Create undirected complete graph
                G = nx.Graph()
                nodes = [(dt_id, dt_info['lat'], dt_info['lon'])] + [(p['pole_id'], p['lat'], p['lon']) for p in p_list]
                for i in range(len(nodes)):
                    for j in range(i + 1, len(nodes)):
                        n1, lat1, lon1 = nodes[i]
                        n2, lat2, lon2 = nodes[j]
                        dist = math.hypot(lat1 - lat2, lon1 - lon2)
                        G.add_edge(n1, n2, weight=dist)
                
                if len(nodes) > 1:
                    mst = nx.minimum_spanning_tree(G)
                    # Direct the tree outwards from DT using BFS
                    edges = nx.bfs_edges(mst, source=dt_id)
                    tree.add_edges_from(edges)
            
            tree.graph['is_geometric'] = not has_wiring
            self.dt_trees[dt_id] = tree
        logger.info(f"Loaded {len(self.dt_trees)} DTs into memory.")

    def get_dt_tree(self, dt_id):
        return self.dt_trees.get(dt_id)

    def get_dt_for_pole(self, pole_id):
        return self.pole_to_dt.get(pole_id)

topology_manager = TopologyManager()
