import pytest
import networkx as nx
from backend.localization import count_affected_poles, has_live_descendants

def test_affected_poles():
    tree = nx.DiGraph()
    tree.add_edges_from([
        ('DT1', 'P1'),
        ('P1', 'P2'),
        ('P2', 'P3'),
        ('P2', 'P4')
    ])
    
    assert count_affected_poles(tree, 'P2') == 3 # P2, P3, P4
    assert count_affected_poles(tree, 'P4') == 1 # Just P4

def test_has_live_descendants():
    tree = nx.DiGraph()
    tree.add_edges_from([
        ('DT1', 'P1'),
        ('P1', 'P2'),
        ('P2', 'P3'),
    ])
    
    # If P2 is dark, but P3 is live -> sensor anomaly
    states = {
        'DT1': 'LIVE',
        'P1': 'LIVE',
        'P2': 'DARK',
        'P3': 'LIVE'
    }
    
    assert has_live_descendants(tree, 'P2', states) == True
    
    # If P3 is also dark -> genuine fault
    states['P3'] = 'DARK'
    assert has_live_descendants(tree, 'P2', states) == False
