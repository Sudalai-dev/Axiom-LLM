import re
from typing import List, Dict, Any

class Chunk:
    def __init__(self, text: str, index: int, metadata: Dict[str, Any]):
        self.text = text
        self.index = index
        self.metadata = metadata

class ChunkEngine:
    """
    ChunkEngine: Slices raw document text into structured semantic blocks.
    Identifies headings, tables, and paragraphs to tag metadata.
    """
    def __init__(self, chunk_size: int = 1000):
        self.chunk_size = chunk_size

    def split(self, text: str) -> List[Chunk]:
        chunks = []
        
        # Identify heading structures (Markdown format e.g. # Heading)
        current_heading = "Root"
        lines = text.split("\n")
        
        buffer = []
        chunk_idx = 0
        
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue
                
            # Detect Heading
            heading_match = re.match(r"^(#{1,6})\s+(.*)$", line_stripped)
            if heading_match:
                # Flush existing buffer before changing headings
                if buffer:
                    chunk_text = "\n".join(buffer)
                    chunks.append(Chunk(
                        text=chunk_text,
                        index=chunk_idx,
                        metadata={"heading": current_heading}
                    ))
                    chunk_idx += 1
                    buffer = []
                current_heading = heading_match.group(2)
                buffer.append(line_stripped)
            
            # Detect Table (Markdown table borders)
            elif line_stripped.startswith("|"):
                buffer.append(line_stripped)
                
            else:
                buffer.append(line_stripped)
                
            # If buffer size limit reached, flush chunk
            if len("\n".join(buffer)) >= self.chunk_size:
                chunk_text = "\n".join(buffer)
                chunks.append(Chunk(
                    text=chunk_text,
                    index=chunk_idx,
                    metadata={"heading": current_heading}
                ))
                chunk_idx += 1
                buffer = []

        # Flush any remaining lines
        if buffer:
            chunk_text = "\n".join(buffer)
            chunks.append(Chunk(
                text=chunk_text,
                index=chunk_idx,
                metadata={"heading": current_heading}
            ))
            
        return chunks
