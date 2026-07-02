import sqlite3
import os
from typing import List, Dict, Any

class KnowledgeGraph:
    """
    KnowledgeGraph: A local-first Graph Database wrapper using SQLite.
    Stores nodes (Concepts) and directed edges (Relationships).
    """
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_graph.db")
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create Concepts (Nodes) table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS concepts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                type TEXT
            )
        """)
        
        # Create Relationships (Edges) table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER,
                target_id INTEGER,
                rel_type TEXT,
                FOREIGN KEY(source_id) REFERENCES concepts(id),
                FOREIGN KEY(target_id) REFERENCES concepts(id),
                UNIQUE(source_id, target_id, rel_type)
            )
        """)
        conn.commit()
        conn.close()

    def add_concept(self, name: str, concept_type: str) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT OR IGNORE INTO concepts (name, type) VALUES (?, ?)", (name, concept_type))
            conn.commit()
            cursor.execute("SELECT id FROM concepts WHERE name = ?", (name,))
            return cursor.fetchone()[0]
        finally:
            conn.close()

    def add_relationship(self, source_name: str, target_name: str, rel_type: str):
        # Ensure concepts exist first
        src_id = self.add_concept(source_name, "Concept")
        tgt_id = self.add_concept(target_name, "Concept")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO relationships (source_id, target_id, rel_type) VALUES (?, ?, ?)",
                (src_id, tgt_id, rel_type)
            )
            conn.commit()
        finally:
            conn.close()

    def query_relations_from(self, concept_name: str) -> List[Dict[str, Any]]:
        """Queries all target concepts and relationship types originating from a node."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT c_target.name, r.rel_type, c_target.type
                FROM concepts c_source
                JOIN relationships r ON c_source.id = r.source_id
                JOIN concepts c_target ON r.target_id = c_target.id
                WHERE c_source.name = ?
            """, (concept_name,))
            rows = cursor.fetchall()
            return [{"target": r[0], "relationship": r[1], "type": r[2]} for r in rows]
        finally:
            conn.close()
