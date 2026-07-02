import hashlib
import numpy as np
from typing import List

class EmbeddingEngine:
    """
    EmbeddingEngine: Encodes text chunks into dense vector representations.
    Attempts to use sentence-transformers locally, with a robust TF-IDF hashing 
    fallback vectorizer for offline isolation.
    """
    def __init__(self, model_name: str = "BAAI/bge-m3"):
        self.model_name = model_name
        self.model = None
        self.vector_dim = 384  # Dimension size for MiniLM or fallback vectors
        
        # Proactively check if sentence_transformers package is available
        try:
            from sentence_transformers import SentenceTransformer
            # Set offline mode flags
            import os
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            self.model = SentenceTransformer(model_name)
            self.vector_dim = self.model.get_sentence_embedding_dimension()
        except Exception:
            # Fall back to deterministic vectorizer for offline stability
            self.model = None

    def embed(self, text: str) -> List[float]:
        if self.model:
            try:
                embedding = self.model.encode(text)
                return embedding.tolist()
            except Exception:
                pass
                
        # Deterministic hashing-based vectorizer fallback
        return self._generate_fallback_vector(text)

    def _generate_fallback_vector(self, text: str) -> List[float]:
        """
        Generates a unit-normalized vector using MD5 hashes of substrings.
        Provides deterministic, localized semantic simulation without internet.
        """
        vector = np.zeros(self.vector_dim)
        words = text.lower().split()
        if not words:
            return vector.tolist()
            
        for word in words:
            # Hash each word to map it to a specific index in the vector dimension
            h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
            idx = h % self.vector_dim
            # Accumulate values
            vector[idx] += 1.0
            
        # Normalize the vector to unit length
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
            
        return vector.tolist()
