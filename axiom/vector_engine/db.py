import numpy as np
from typing import List, Dict, Any, Optional

class VectorRecord:
    def __init__(self, record_id: str, vector: List[float], payload: Dict[str, Any], project_id: int):
        self.record_id = record_id
        self.vector = np.array(vector, dtype=np.float32)
        self.payload = payload
        self.project_id = project_id

class VectorEngine:
    """
    VectorEngine: A custom, local vector database implementation.
    Manages vector records, computes cosine similarity, and filters queries by project ID.
    """
    def __init__(self):
        # In-memory storage for local vector records
        self.records: Dict[str, VectorRecord] = {}

    def insert(self, record_id: str, vector: List[float], payload: Dict[str, Any], project_id: int):
        self.records[record_id] = VectorRecord(record_id, vector, payload, project_id)

    def delete(self, record_id: str):
        if record_id in self.records:
            del self.records[record_id]

    def search(self, query_vector: List[float], project_id: int, limit: int = 5, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        q_vec = np.array(query_vector, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        
        results = []
        
        for rec in self.records.values():
            # Project Isolation Filter
            if rec.project_id != project_id:
                continue
                
            # Payload Metadata Filters
            if filters:
                match = True
                for k, v in filters.items():
                    if rec.payload.get(k) != v:
                        match = False
                        break
                if not match:
                    continue
            
            # Compute Cosine Similarity
            rec_norm = np.linalg.norm(rec.vector)
            if q_norm == 0 or rec_norm == 0:
                similarity = 0.0
            else:
                similarity = float(np.dot(q_vec, rec.vector) / (q_norm * rec_norm))
                
            results.append({
                "id": rec.record_id,
                "score": similarity,
                "payload": rec.payload
            })

        # Rank records by descending similarity score
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]
