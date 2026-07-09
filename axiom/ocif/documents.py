"""Builds exportable document artifacts (markdown, structured JSON) from a
finished SolutionDocument. Pure formatting — no new reasoning."""

import json
import re
from typing import List

from pydantic import Field

from core.models.base import OCIFBaseModel
from ocif.frames import SolutionDocument


class GeneratedDocument(OCIFBaseModel):
    type: str = "markdown"
    title: str = ""
    filename: str = ""
    content: str = ""


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
    return slug or "solution"


def build_generated_documents(doc: SolutionDocument, markdown: str) -> List[GeneratedDocument]:
    slug = slugify(doc.title)
    return [
        GeneratedDocument(type="markdown", title=doc.title, filename=f"{slug}.md", content=markdown),
        GeneratedDocument(
            type="json", title=f"{doc.title} (structured)", filename=f"{slug}.json",
            content=json.dumps(doc.model_dump(), indent=2, default=str),
        ),
    ]
