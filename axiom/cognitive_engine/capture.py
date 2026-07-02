import os
import re
from typing import Dict, Any, List

class CaptureLayer:
    """
    Layer 2: Capture.
    Harvests context from local files, documentation, and metadata matching the query.
    Simulates a vector store/knowledge base search using direct file scanning of workspace files.
    """
    def __init__(self, workspace_path: str = "D:\\Tasks\\Axiom - LLM"):
        self.workspace_path = workspace_path

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        query = payload.get("query", "")
        keywords = [word.lower() for word in re.findall(r"\b\w{4,}\b", query)]
        
        context_chunks: List[Dict[str, Any]] = []

        # Scan workspace md files for real context harvesting (local RAG implementation)
        if os.path.exists(self.workspace_path):
            for file_name in os.listdir(self.workspace_path):
                if file_name.endswith(".md"):
                    file_path = os.path.join(self.workspace_path, file_name)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            lines = f.readlines()
                            # Search for lines containing keywords
                            chunk_lines = []
                            for idx, line in enumerate(lines):
                                if any(kw in line.lower() for kw in keywords):
                                    # Grab context around the match (+- 3 lines)
                                    start = max(0, idx - 3)
                                    end = min(len(lines), idx + 4)
                                    snippet = "".join(lines[start:end])
                                    context_chunks.append({
                                        "source": file_name,
                                        "line_number": idx + 1,
                                        "content": snippet.strip()
                                    })
                                    # Limit context chunks to avoid bloating
                                    if len(context_chunks) >= 10:
                                        break
                    except Exception as e:
                        # Log error internally and continue
                        pass
        
        payload["captured_context"] = context_chunks
        return payload
