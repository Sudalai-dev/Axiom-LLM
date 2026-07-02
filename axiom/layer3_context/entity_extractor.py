"""
OCIF Named Entity Extractor — Layer 3.

Performs light lexical Named Entity Recognition (NER) to parse technical systems,
protocols, databases, and architectural concepts referenced in user queries.

Traces to:
  - Document 6 (LLD) Section 3.1: Context Intelligence Components
  - Document 7 (LLD) Section 4: Context Layer contract
"""

import logging
import re
from typing import List

from axiom.core.models.context import EntityInfo

logger = logging.getLogger("AxiomEntityExtractor")


class EntityExtractor:
    """
    Scans query text to extract technology domains, databases, and protocols.
    """

    # Extended technology entity vocabulary mapping to types
    VOCABULARY = {
        # Protocols
        "mqtt": "Protocol",
        "kafka": "Protocol",
        "grpc": "Protocol",
        "http": "Protocol",
        "https": "Protocol",
        "tls": "Protocol",
        "tcp": "Protocol",
        
        # Databases
        "postgresql": "Database",
        "postgres": "Database",
        "sqlite": "Database",
        "pinecone": "Database",
        "redis": "Database",
        "qdrant": "Database",
        "chromadb": "Database",
        "mongodb": "Database",
        "mysql": "Database",
        
        # Services & Frameworks
        "fastapi": "Service",
        "flask": "Service",
        "django": "Service",
        "nextjs": "Service",
        "react": "Service",
        "next": "Service",
        "api": "Service",
        "microservice": "Service",
        
        # DevOps & Deployment
        "docker": "DevOps",
        "kubernetes": "DevOps",
        "k8s": "DevOps",
        "eks": "DevOps",
        "terraform": "DevOps",
        "helm": "DevOps",
        "ansible": "DevOps",
        "aws": "DevOps"
    }

    def extract(self, query: str) -> List[EntityInfo]:
        """
        Tokenizes query, matches words against technical dictionary, 
        and constructs EntityInfo objects.
        """
        extracted_entities = []
        seen_terms = set()
        
        # Tokenize by alphanumeric bounds
        words = re.findall(r"\b[a-zA-Z0-9_\-\.]+\b", query.lower())
        
        for word in words:
            # Check dictionary match
            if word in self.VOCABULARY and word not in seen_terms:
                term_canonical = word.upper() if len(word) <= 4 else word.capitalize()
                # Special cases
                if word == "postgres":
                    term_canonical = "PostgreSQL"
                elif word == "k8s":
                    term_canonical = "Kubernetes"
                elif word == "nextjs":
                    term_canonical = "Next.js"
                
                entity_type = self.VOCABULARY[word]
                
                extracted_entities.append(
                    EntityInfo(
                        term=term_canonical,
                        type=entity_type,
                        confidence=0.95
                    )
                )
                seen_terms.add(word)

        logger.debug(f"Extracted entities: {[e.term for e in extracted_entities]}")
        return extracted_entities
