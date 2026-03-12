"""
Graph Intelligence Service – NetworkX graph-based financial crime detection.
Computes degree centrality, PageRank, shortest path to sanctioned entities, and community detection.
"""
import logging
import random
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

import networkx as nx
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(name)s – %(message)s")
logger = logging.getLogger(__name__)

_graph: Optional[nx.DiGraph] = None
_sanctioned_nodes: set = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _graph, _sanctioned_nodes
    _graph, _sanctioned_nodes = build_sample_graph()
    logger.info(f"✅ Graph loaded: {_graph.number_of_nodes()} nodes, {_graph.number_of_edges()} edges")
    yield


def build_sample_graph() -> Tuple[nx.DiGraph, set]:
    """
    Build a representative financial crime network graph for demonstration.
    In production: loaded from Neo4j / graph database.
    """
    G = nx.DiGraph()

    # Add legitimate clients
    for i in range(1, 101):
        G.add_node(f"CL{i:05d}", type="client", risk=random.uniform(10, 40))

    # Add companies
    for i in range(1, 21):
        G.add_node(f"CORP{i:03d}", type="company", risk=random.uniform(20, 60))

    # Offshore/risky entities
    sanctioned = {"SHADOW_CORP_01", "GHOST_SHELL_AE", "OFFSHORE_KP_001"}
    for s in sanctioned:
        G.add_node(s, type="sanctioned_entity", risk=100)

    # Add transaction edges
    for i in range(1, 101):
        for _ in range(random.randint(1, 5)):
            target = f"CL{random.randint(1, 100):05d}"
            if target != f"CL{i:05d}":
                G.add_edge(f"CL{i:05d}", target, type="transaction", amount=random.uniform(1000, 500000))

    # Add connections to offshore
    for s in sanctioned:
        # Connect 10-15 clients to sanctioned entities (money laundering network)
        for _ in range(random.randint(10, 15)):
            client = f"CL{random.randint(1, 100):05d}"
            G.add_edge(client, s, type="transaction")

    # Add ownership edges  
    for i in range(1, 21):
        for _ in range(random.randint(1, 3)):
            client = f"CL{random.randint(1, 100):05d}"
            G.add_edge(client, f"CORP{i:03d}", type="ownership")

    return G, sanctioned


app = FastAPI(
    title="Graph Intelligence Service",
    description="NetworkX graph analysis for financial crime network detection",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
router = APIRouter()


class GraphRiskRequest(BaseModel):
    client_id: str
    include_network_analysis: bool = True


class GraphRiskResponse(BaseModel):
    client_id: str
    graph_risk_score: float = Field(..., ge=0, le=100)
    degree_centrality: float = 0.0
    page_rank: float = 0.0
    distance_to_sanctioned: Optional[int] = None
    network_cluster_size: int = 0
    top_risky_connections: List[str] = Field(default_factory=list)
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)


class GraphAnalyzer:
    """Performs graph-based risk analysis on the financial network."""

    def analyze(self, client_id: str) -> Dict[str, Any]:
        global _graph, _sanctioned_nodes

        # Add the new client to graph if not present
        if client_id not in _graph:
            _graph.add_node(client_id, type="client", risk=30)
            # Add some random connections for simulation
            n_connections = random.randint(1, 8)
            for _ in range(n_connections):
                target = f"CL{random.randint(1, 100):05d}"
                _graph.add_edge(client_id, target, type="transaction")

        G_undirected = _graph.to_undirected()

        # Degree centrality
        centrality = nx.degree_centrality(G_undirected)
        degree_centrality = centrality.get(client_id, 0.0)

        # PageRank
        pagerank = nx.pagerank(_graph, alpha=0.85, max_iter=100)
        page_rank_score = pagerank.get(client_id, 0.0)

        # Shortest path to sanctioned entities
        distance_to_sanctioned = None
        for sanctioned in _sanctioned_nodes:
            if sanctioned in G_undirected:
                try:
                    path_len = nx.shortest_path_length(G_undirected, client_id, sanctioned)
                    if distance_to_sanctioned is None or path_len < distance_to_sanctioned:
                        distance_to_sanctioned = path_len
                except nx.NetworkXNoPath:
                    continue

        # Community detection (Louvain approximation via label propagation)
        cluster_size = 1
        try:
            communities = list(nx.community.label_propagation_communities(G_undirected))
            for community in communities:
                if client_id in community:
                    cluster_size = len(community)
                    break
        except Exception:
            cluster_size = G_undirected.degree(client_id) + 1

        # Risky connections
        neighbors = list(_graph.successors(client_id)) + list(_graph.predecessors(client_id))
        risky_connections = [
            n for n in neighbors
            if _graph.nodes.get(n, {}).get("risk", 0) > 60 or n in _sanctioned_nodes
        ][:5]

        # Compute composite graph risk score
        score = self._compute_graph_score(
            degree_centrality, page_rank_score, distance_to_sanctioned,
            cluster_size, len(risky_connections)
        )

        return {
            "client_id": client_id,
            "graph_risk_score": round(score, 2),
            "degree_centrality": round(degree_centrality, 4),
            "page_rank": round(page_rank_score, 6),
            "distance_to_sanctioned": distance_to_sanctioned,
            "network_cluster_size": cluster_size,
            "top_risky_connections": risky_connections,
        }

    def _compute_graph_score(
        self,
        centrality: float,
        pagerank: float,
        dist_sanctioned: Optional[int],
        cluster_size: int,
        risky_conn_count: int,
    ) -> float:
        score = 0.0

        # Centrality contribution (0-25 pts)
        score += min(centrality * 250, 25)

        # PageRank contribution (0-15 pts)
        score += min(pagerank * 150_000, 15)

        # Proximity to sanctioned entity (0-40 pts)
        if dist_sanctioned is not None:
            if dist_sanctioned == 1:
                score += 40
            elif dist_sanctioned == 2:
                score += 30
            elif dist_sanctioned == 3:
                score += 20
            elif dist_sanctioned <= 5:
                score += 10

        # Cluster size (0-10 pts)
        if cluster_size > 50:
            score += 10
        elif cluster_size > 20:
            score += 7
        elif cluster_size > 10:
            score += 4

        # Risky connections (0-10 pts)
        score += min(risky_conn_count * 2, 10)

        return min(score, 100.0)


_analyzer = GraphAnalyzer()


@router.post("/graph/risk", response_model=GraphRiskResponse)
async def analyze_graph_risk(request: GraphRiskRequest) -> GraphRiskResponse:
    result = _analyzer.analyze(request.client_id)
    return GraphRiskResponse(**result)


@router.get("/graph/stats")
async def graph_stats():
    if _graph is None:
        return {"error": "Graph not initialized"}
    return {
        "nodes": _graph.number_of_nodes(),
        "edges": _graph.number_of_edges(),
        "sanctioned_nodes": len(_sanctioned_nodes),
    }


@router.get("/health")
async def health():
    return {"status": "healthy", "service": "graph-intelligence"}


app.include_router(router, prefix="/api/v1", tags=["Graph Intelligence"])
