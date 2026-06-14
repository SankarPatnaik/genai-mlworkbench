import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Set, Tuple

from app.config import settings

try:
    from neo4j import GraphDatabase
except Exception:
    GraphDatabase = None


STOP_ENTITIES = {
    "The", "This", "That", "These", "Those", "There", "Here", "When", "Where",
    "What", "Which", "Who", "Why", "How", "Context", "Document", "Section",
}


class KnowledgeGraphService:
    def __init__(self):
        self.driver = None
        self.memory_graph = {}
        if GraphDatabase and settings.NEO4J_URI:
            try:
                self.driver = GraphDatabase.driver(
                    settings.NEO4J_URI,
                    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                )
                self.driver.verify_connectivity()
            except Exception as exc:
                print(f"Neo4j unavailable, using in-memory context graph: {exc}")
                self.driver = None

    def is_available(self) -> bool:
        if not self.driver:
            return False
        try:
            self.driver.verify_connectivity()
            return True
        except Exception:
            return False

    def mode(self) -> str:
        return "neo4j" if self.is_available() else "memory"

    def build_graph(self, document_id: str, chunks: List[Dict[str, Any]], max_entities_per_chunk: int = 12) -> Dict[str, Any]:
        nodes: Dict[str, Dict[str, Any]] = {}
        edges: Counter[Tuple[str, str, str]] = Counter()
        chunk_links: List[Dict[str, Any]] = []

        for chunk in chunks:
            chunk_index = int(chunk.get("index", 0))
            text = chunk.get("text", "")
            entities = self._extract_entities(text, max_entities_per_chunk)

            for entity in entities:
                key = self._entity_key(entity)
                node = nodes.setdefault(key, {"id": key, "label": entity, "type": "Entity", "mentions": 0})
                node["mentions"] += 1
                chunk_links.append({"entity_id": key, "chunk_index": chunk_index})

            for left, right in self._entity_pairs(entities):
                edges[(self._entity_key(left), "CO_OCCURS_WITH", self._entity_key(right))] += 1

            for subject, relation, target in self._extract_relation_phrases(text):
                subject_key = self._entity_key(subject)
                target_key = self._entity_key(target)
                nodes.setdefault(subject_key, {"id": subject_key, "label": subject, "type": "Entity", "mentions": 1})
                nodes.setdefault(target_key, {"id": target_key, "label": target, "type": "Entity", "mentions": 1})
                edges[(subject_key, relation, target_key)] += 2

        graph = {
            "document_id": document_id,
            "nodes": list(nodes.values()),
            "edges": [
                {"source": source, "relationship": rel, "target": target, "weight": weight}
                for (source, rel, target), weight in edges.items()
            ],
            "chunk_links": chunk_links,
        }

        if self.driver:
            self._persist_neo4j(graph)
        else:
            self.memory_graph[document_id] = graph

        return self._summary(graph)

    def query_context(self, document_id: str, query: str, max_entities: int = 8, max_chunks: int = 3) -> Dict[str, Any]:
        graph = self._load_graph(document_id)
        if not graph:
            return {"entities": [], "relationships": [], "chunk_indices": [], "context_summary": ""}

        query_terms = set(self._normalize_token(token) for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]+", query))
        query_terms.discard("")

        scored_nodes = []
        for node in graph["nodes"]:
            label_terms = set(self._normalize_token(token) for token in node["label"].split())
            overlap = len(query_terms & label_terms)
            if overlap:
                scored_nodes.append((overlap + node.get("mentions", 0) * 0.1, node))

        if not scored_nodes:
            scored_nodes = [(node.get("mentions", 0), node) for node in graph["nodes"]]

        top_nodes = [node for _, node in sorted(scored_nodes, key=lambda item: item[0], reverse=True)[:max_entities]]
        top_ids = {node["id"] for node in top_nodes}

        relationships = [
            edge for edge in graph["edges"]
            if edge["source"] in top_ids or edge["target"] in top_ids
        ][: max_entities * 2]

        chunk_scores = Counter()
        for link in graph["chunk_links"]:
            if link["entity_id"] in top_ids:
                chunk_scores[link["chunk_index"]] += 1
        chunk_indices = [idx for idx, _ in chunk_scores.most_common(max_chunks)]

        relationship_lines = [
            f"{self._label_for(graph, edge['source'])} {edge['relationship'].replace('_', ' ').lower()} {self._label_for(graph, edge['target'])}"
            for edge in relationships[:8]
        ]

        return {
            "entities": top_nodes,
            "relationships": relationships,
            "chunk_indices": chunk_indices,
            "context_summary": "\n".join(relationship_lines),
        }

    def _persist_neo4j(self, graph: Dict[str, Any]) -> None:
        with self.driver.session() as session:
            session.run(
                "MATCH ()-[r:RELATED_TO {document_id: $document_id}]->() DELETE r",
                document_id=graph["document_id"],
            )
            session.run(
                "MATCH (c:Chunk {document_id: $document_id}) DETACH DELETE c",
                document_id=graph["document_id"],
            )
            session.run("MATCH (d:Document {id: $document_id}) DETACH DELETE d", document_id=graph["document_id"])
            session.run("MERGE (:Document {id: $document_id})", document_id=graph["document_id"])
            for node in graph["nodes"]:
                session.run(
                    """
                    MERGE (e:Entity {id: $id})
                    SET e.label = $label, e.mentions = $mentions
                    WITH e
                    MATCH (d:Document {id: $document_id})
                    MERGE (d)-[:HAS_ENTITY]->(e)
                    """,
                    id=node["id"],
                    label=node["label"],
                    mentions=node["mentions"],
                    document_id=graph["document_id"],
                )
            for edge in graph["edges"]:
                session.run(
                    """
                    MATCH (s:Entity {id: $source})
                    MATCH (t:Entity {id: $target})
                    MERGE (s)-[r:RELATED_TO {document_id: $document_id, name: $relationship}]->(t)
                    SET r.weight = $weight
                    """,
                    source=edge["source"],
                    target=edge["target"],
                    relationship=edge["relationship"],
                    weight=edge["weight"],
                    document_id=graph["document_id"],
                )
            for link in graph["chunk_links"]:
                session.run(
                    """
                    MATCH (e:Entity {id: $entity_id})
                    MERGE (c:Chunk {id: $chunk_id})
                    SET c.index = $chunk_index, c.document_id = $document_id
                    MERGE (e)-[:MENTIONED_IN]->(c)
                    """,
                    entity_id=link["entity_id"],
                    chunk_id=f"{graph['document_id']}:{link['chunk_index']}",
                    chunk_index=link["chunk_index"],
                    document_id=graph["document_id"],
                )

    def _load_graph(self, document_id: str) -> Dict[str, Any]:
        if not self.driver:
            return self.memory_graph.get(document_id, {})

        with self.driver.session() as session:
            nodes = [
                {"id": record["id"], "label": record["label"], "type": "Entity", "mentions": record["mentions"]}
                for record in session.run(
                    """
                    MATCH (:Document {id: $document_id})-[:HAS_ENTITY]->(e:Entity)
                    RETURN e.id AS id, e.label AS label, coalesce(e.mentions, 1) AS mentions
                    """,
                    document_id=document_id,
                )
            ]
            edges = [
                {
                    "source": record["source"],
                    "relationship": record["relationship"],
                    "target": record["target"],
                    "weight": record["weight"],
                }
                for record in session.run(
                    """
                    MATCH (s:Entity)-[r:RELATED_TO {document_id: $document_id}]->(t:Entity)
                    RETURN s.id AS source, r.name AS relationship, t.id AS target, coalesce(r.weight, 1) AS weight
                    """,
                    document_id=document_id,
                )
            ]
            chunk_links = [
                {"entity_id": record["entity_id"], "chunk_index": record["chunk_index"]}
                for record in session.run(
                    """
                    MATCH (:Document {id: $document_id})-[:HAS_ENTITY]->(e:Entity)-[:MENTIONED_IN]->(c:Chunk {document_id: $document_id})
                    RETURN e.id AS entity_id, c.index AS chunk_index
                    """,
                    document_id=document_id,
                )
            ]
        return {"document_id": document_id, "nodes": nodes, "edges": edges, "chunk_links": chunk_links}

    def _summary(self, graph: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "document_id": graph["document_id"],
            "graph_store": self.mode(),
            "nodes_count": len(graph["nodes"]),
            "edges_count": len(graph["edges"]),
            "chunk_links_count": len(graph["chunk_links"]),
            "top_entities": sorted(graph["nodes"], key=lambda node: node["mentions"], reverse=True)[:10],
        }

    def _extract_entities(self, text: str, limit: int) -> List[str]:
        candidates = re.findall(r"\b(?:[A-Z][A-Za-z0-9&.-]+(?:\s+[A-Z][A-Za-z0-9&.-]+){0,4})\b", text)
        counts = Counter(candidate.strip() for candidate in candidates if candidate.strip() not in STOP_ENTITIES)
        return [entity for entity, _ in counts.most_common(limit)]

    def _extract_relation_phrases(self, text: str) -> List[Tuple[str, str, str]]:
        patterns = [
            (r"([A-Z][A-Za-z0-9&.-]+(?:\s+[A-Z][A-Za-z0-9&.-]+){0,3})\s+(requires|contains|includes|uses|depends on|governs|defines)\s+([A-Z][A-Za-z0-9&.-]+(?:\s+[A-Z][A-Za-z0-9&.-]+){0,3})", None),
        ]
        relations = []
        for pattern, _ in patterns:
            for subject, relation, target in re.findall(pattern, text):
                relations.append((subject.strip(), relation.upper().replace(" ", "_"), target.strip()))
        return relations[:20]

    def _entity_pairs(self, entities: List[str]) -> Set[Tuple[str, str]]:
        pairs = set()
        for idx, left in enumerate(entities):
            for right in entities[idx + 1: idx + 4]:
                pairs.add(tuple(sorted((left, right))))
        return pairs

    def _entity_key(self, entity: str) -> str:
        return self._normalize_token(entity.replace(" ", "_"))

    def _normalize_token(self, value: str) -> str:
        return re.sub(r"[^a-z0-9_]+", "", value.lower().strip())

    def _label_for(self, graph: Dict[str, Any], node_id: str) -> str:
        for node in graph["nodes"]:
            if node["id"] == node_id:
                return node["label"]
        return node_id


knowledge_graph_service = KnowledgeGraphService()
