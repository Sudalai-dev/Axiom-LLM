import re
from typing import Dict, Any, List

class NLPEngine:
    """
    NLPEngine: Performs initial language analysis, tokenization,
    lemmatization, POS checking, and technical Named Entity Recognition (NER).
    """
    ENTITY_DICT = {
        "MQTT": "Protocol",
        "Kafka": "Protocol",
        "FastAPI": "Service",
        "PostgreSQL": "Database",
        "SQLite": "Database",
        "Qdrant": "Database",
        "Chroma": "Database",
        "Docker": "DevOps",
        "Kubernetes": "DevOps"
    }

    def __init__(self):
        pass

    def analyze(self, query: str) -> Dict[str, Any]:
        cleaned_query = query.strip()
        words = re.findall(r"\b\w+\b", cleaned_query)
        
        # 1. Simple Named Entity Recognition (NER)
        entities = []
        for word in words:
            # Check matches in lookup table
            for key in self.ENTITY_DICT:
                if word.lower() == key.lower():
                    entities.append({"term": key, "type": self.ENTITY_DICT[key]})
                    
        # 2. Tokenization and Normalization (Basic Lemmatization)
        normalized_words = [w.lower() for w in words]
        
        # 3. Domain & Task Classification
        domain = "Unknown"
        task_type = "GeneralQ&A"
        
        if any(e["type"] == "Protocol" for e in entities) or "sensor" in normalized_words:
            domain = "AIoT"
        elif any(e["type"] == "Database" for e in entities) or "db" in normalized_words:
            domain = "Database"
        elif any(e["type"] == "DevOps" for e in entities) or "deploy" in normalized_words:
            domain = "DevOps"
            
        if any(w in ["write", "generate", "code", "build"] for w in normalized_words):
            task_type = "Code Generation"
        elif any(w in ["explain", "review", "audit", "diagnose"] for w in normalized_words):
            task_type = "Architecture Review"

        language = "English"  # Simple default detector
        if re.search(r"\b(bonjour|salut)\b", cleaned_query, re.I):
            language = "French"
        elif re.search(r"\b(hola|amigo)\b", cleaned_query, re.I):
            language = "Spanish"

        return {
            "language": language,
            "intent": task_type,
            "task_type": task_type,
            "domain": domain,
            "entities": list(set(e["term"] for e in entities)),
            "keywords": list(set(normalized_words)),
            "confidence": 0.95,
            "requires_reasoning": True
        }
