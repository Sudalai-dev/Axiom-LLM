"""
Knowledge Ingestor — turns real documents into pending knowledge.

Reuses the dependency-light, self-contained multi-format extractor from
`datasets.ingestion` (markdown/pdf/docx/pptx/xlsx/csv/code/plain-text, with
graceful degradation) and the markdown-aware `knowledge.chunker.ChunkEngine`.
The result is submitted to the repository's **pending queue** — nothing an
ingestion produces ever becomes active knowledge without human approval.
"""

import os
import uuid
from typing import Any, Dict, List, Optional

from datasets.ingestion import (
    _classify_document,
    _detect_format,
    _extract_entities,
    _extract_text_content,
)
from ecosystem.models import GLOBAL_TENANT, KnowledgeCategory, KnowledgeObject, new_id
from ecosystem.repository import EngineeringKnowledgeRepository
from knowledge.chunker import ChunkEngine

# Map the ingestion classifier's document categories onto knowledge categories.
_DOC_CATEGORY_MAP = {
    "architecture_diagram": KnowledgeCategory.DIAGRAM.value,
    "meeting_notes": KnowledgeCategory.DOCUMENT.value,
    "lessons_learned": KnowledgeCategory.LESSON_LEARNED.value,
    "engineering_decision": KnowledgeCategory.DOCUMENT.value,
    "incident_report": KnowledgeCategory.FAILURE_MODE.value,
    "design_review": KnowledgeCategory.DOCUMENT.value,
    "specification": KnowledgeCategory.DOCUMENT.value,
}


class KnowledgeIngestor:
    def __init__(self, repository: EngineeringKnowledgeRepository) -> None:
        self.repository = repository
        self.chunker = ChunkEngine()

    def _build_object(self, text: str, title: str, domain: str, industry: str,
                      category: str, tenant_id: str, source: str, entities: List[str]) -> KnowledgeObject:
        chunks = self.chunker.split(text) if text else []
        return KnowledgeObject(
            knowledge_id=new_id(),
            title=title,
            category=category,
            domain=domain,
            industry=industry,
            summary=(text[:400] if text else title),
            body=text,
            confidence=0.8 if text else 0.5,
            author="ingestion",
            tenant_id=tenant_id,
            source_document=source,
            tags=["ingested"] + entities[:8],
            attributes={
                "chunk_count": len(chunks),
                "chunk_headings": [c.metadata.get("heading", "") for c in chunks][:20],
                "extracted_entities": entities,
                "source": source,
            },
        )

    def ingest_text(
        self,
        text: str,
        title: str,
        domain: str = "",
        industry: str = "",
        category: Optional[str] = None,
        tenant_id: str = GLOBAL_TENANT,
        submitted_by: str = "",
        source: str = "inline",
    ) -> str:
        """Ingest raw text into the pending queue. Returns the pending id."""
        classification = _classify_document(text or "", title or "document.txt")
        obj = self._build_object(
            text=text or "",
            title=title or "Untitled Knowledge",
            domain=domain or classification["domain"],
            industry=industry or classification["industry"],
            category=category or _DOC_CATEGORY_MAP.get(classification["category"], KnowledgeCategory.DOCUMENT.value),
            tenant_id=tenant_id,
            source=source,
            entities=_extract_entities(text or ""),
        )
        return self.repository.submit_pending(obj, submitted_by=submitted_by)

    def ingest_file(
        self,
        file_path: str,
        tenant_id: str = GLOBAL_TENANT,
        submitted_by: str = "",
    ) -> Optional[str]:
        """Ingest a file into the pending queue. Returns the pending id, or
        None if the file is missing."""
        if not os.path.exists(file_path):
            return None
        fmt = _detect_format(file_path)
        text = _extract_text_content(file_path, fmt)
        classification = _classify_document(text or "", file_path)
        obj = self._build_object(
            text=text or "",
            title=os.path.basename(file_path),
            domain=classification["domain"],
            industry=classification["industry"],
            category=_DOC_CATEGORY_MAP.get(classification["category"], KnowledgeCategory.DOCUMENT.value),
            tenant_id=tenant_id,
            source=file_path,
            entities=_extract_entities(text or ""),
        )
        return self.repository.submit_pending(obj, submitted_by=submitted_by)
