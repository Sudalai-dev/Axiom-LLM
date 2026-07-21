"""Octagon visualization: the 8-engine execution rendered as an actual SVG diagram."""

import asyncio

from ocif import OctagonalKernel
from ocif.frames import EngineName, EngineResult, EngineStatus
from ocif.octagon import ENGINE_ORDER, build_octagon_svg


def run(coro):
    return asyncio.run(coro)


def _fake_timeline(skip_knowledge: bool = False):
    timeline = []
    for name in ENGINE_ORDER:
        status = EngineStatus.SKIPPED if (skip_knowledge and name == "knowledge") else EngineStatus.COMPLETED
        timeline.append(EngineResult(engine=EngineName(name), status=status, duration_ms=12.5))
    return timeline


def test_build_octagon_svg_renders_all_eight_vertices():
    svg = build_octagon_svg(_fake_timeline(), confidence=0.87)
    assert svg.startswith("<svg")
    assert svg.count('r="30"') == 8  # one node circle per engine
    for name in ENGINE_ORDER:
        assert name.capitalize() in svg or name.title() in svg


def test_build_octagon_svg_shows_skipped_engine_distinctly():
    svg_normal = build_octagon_svg(_fake_timeline(skip_knowledge=False), confidence=0.8)
    svg_skipped = build_octagon_svg(_fake_timeline(skip_knowledge=True), confidence=0.8)
    assert "skipped" not in svg_normal
    assert "skipped" in svg_skipped
    assert "stroke-dasharray" in svg_skipped


def test_build_octagon_svg_handles_partial_timeline():
    """A trivial-request short-circuit only runs Perception + Context —
    the octagon must still render all 8 vertices without crashing."""
    partial = [
        EngineResult(engine=EngineName.PERCEPTION, status=EngineStatus.COMPLETED, duration_ms=2.0),
        EngineResult(engine=EngineName.CONTEXT, status=EngineStatus.COMPLETED, duration_ms=1.5),
    ]
    svg = build_octagon_svg(partial, confidence=0.0)
    assert svg.count('r="30"') == 8
    assert "pending" in svg


def test_kernel_engineering_request_produces_valid_octagon_svg_in_trace():
    kernel = OctagonalKernel()
    out = run(kernel.process(
        "Design an MQTT-based industrial sensor alerting platform for a factory",
        user_id="t1",
    ))
    assert not out.is_conversational
    svg = out.trace.octagon_svg
    assert svg.startswith("<svg")
    assert svg.count('r="30"') == 8
    assert str(round(out.confidence * 100)) + "%" in svg


def test_kernel_trivial_request_still_produces_octagon_svg():
    kernel = OctagonalKernel()
    out = run(kernel.process("hello"))
    assert out.is_conversational
    assert out.trace.octagon_svg.startswith("<svg")
