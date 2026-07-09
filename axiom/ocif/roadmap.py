"""
Structures the flat `SolutionDocument.implementation_roadmap` (phase + items)
into a richer, dependency-aware roadmap: phases carry an extracted timeline,
individual tasks, and explicit phase-to-phase dependencies. Pure
post-processing of already user-facing content — no new reasoning.
"""

import re
from typing import List

from pydantic import Field

from core.models.base import OCIFBaseModel
from ocif.frames import RoadmapPhase


class RoadmapTask(OCIFBaseModel):
    name: str = ""
    dependencies: List[str] = Field(default_factory=list)


class RoadmapPhaseDetailed(OCIFBaseModel):
    phase: str = ""
    timeline: str = ""
    tasks: List[RoadmapTask] = Field(default_factory=list)
    depends_on: List[str] = Field(default_factory=list)


class ImplementationRoadmap(OCIFBaseModel):
    phases: List[RoadmapPhaseDetailed] = Field(default_factory=list)


_TIMELINE_SUFFIX = re.compile(r"\(([^)]+)\)\s*$")


def build_implementation_roadmap(phases: List[RoadmapPhase]) -> ImplementationRoadmap:
    """Extracts an explicit timeline from each phase heading (e.g. the
    already-generated 'Phase 1 — Foundation (weeks 1-2)') and chains each
    phase's dependency on the one before it."""
    detailed: List[RoadmapPhaseDetailed] = []
    prior_name = None

    for phase in phases:
        match = _TIMELINE_SUFFIX.search(phase.phase)
        timeline = match.group(1) if match else ""
        name = _TIMELINE_SUFFIX.sub("", phase.phase).strip()
        depends_on = [prior_name] if prior_name else []
        tasks = [RoadmapTask(name=item, dependencies=list(depends_on)) for item in phase.items]

        detailed.append(RoadmapPhaseDetailed(
            phase=name, timeline=timeline, tasks=tasks, depends_on=depends_on,
        ))
        prior_name = name

    return ImplementationRoadmap(phases=detailed)
