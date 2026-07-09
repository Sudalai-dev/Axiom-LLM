"""
Ephemeral, bounded, in-process cache of recently produced Solution Blueprints,
keyed by solution_id. Backs the on-demand document/export endpoints so a
client can fetch an HLD, a PDF-manifest entry, or the raw JSON for a
solution it just received, without resending the whole blueprint.

Deliberately in-memory only (like the OCIF Memory Engine's working/
conversation slices) — a solution is trivially re-derivable by re-issuing
the same request, so there's no need for durable storage here the way
there is for the learning store.
"""

import threading
from collections import OrderedDict
from typing import Optional, Tuple

from ocif.frames import SolutionDocument

_MAX_ENTRIES = 500

_lock = threading.Lock()
_cache: "OrderedDict[str, Tuple[SolutionDocument, str]]" = OrderedDict()


def put(doc: SolutionDocument, markdown: str) -> None:
    with _lock:
        _cache[doc.solution_id] = (doc, markdown)
        _cache.move_to_end(doc.solution_id)
        while len(_cache) > _MAX_ENTRIES:
            _cache.popitem(last=False)


def get(solution_id: str) -> Optional[Tuple[SolutionDocument, str]]:
    with _lock:
        entry = _cache.get(solution_id)
        if entry:
            _cache.move_to_end(solution_id)
        return entry


def clear() -> None:
    """Test-only helper."""
    with _lock:
        _cache.clear()
