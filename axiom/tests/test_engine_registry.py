import pytest
from core.contracts import IParserEngine, IChunkEngine
from core.engine_registry import engine_registry
from knowledge.parser import ParserEngine
from knowledge.chunker import ChunkEngine


def test_engine_registry_resolves_defaults():
    # 1. Resolve default implementations
    parser = engine_registry.resolve(IParserEngine)
    chunker = engine_registry.resolve(IChunkEngine)

    assert isinstance(parser, ParserEngine)
    assert isinstance(chunker, ChunkEngine)

    # 2. Check singleton behavior (resolving again returns the same instance)
    parser_second = engine_registry.resolve(IParserEngine)
    assert parser is parser_second


def test_engine_registry_custom_registration():
    # 1. Define a mock parser implementing IParserEngine
    class MockParser(IParserEngine):
        def parse(self, filepath: str) -> str:
            return "Mock parsed text"

    # 2. Register mock parser implementation
    engine_registry.register(IParserEngine, MockParser)

    # 3. Resolve and assert mock behaves correctly
    resolved_mock = engine_registry.resolve(IParserEngine)
    assert isinstance(resolved_mock, MockParser)
    assert resolved_mock.parse("dummy_path") == "Mock parsed text"

    # 4. Clean up / Restore defaults
    engine_registry.register(IParserEngine, ParserEngine)
