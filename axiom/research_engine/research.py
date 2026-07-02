from typing import Dict, Any, List

class ResearchEngine:
    """
    ResearchEngine: Crawls trusted specifications and official docs when requested.
    Saves external findings separately to avoid contaminating internal files.
    """
    def __init__(self):
        self.external_docs: List[Dict[str, Any]] = []

    def execute_online_research(self, topic: str, search_fn) -> Dict[str, Any]:
        """
        Executes search using search_web tool and parses metadata,
        storing findings in a separate memory index.
        """
        # Call the search web tool
        search_query = f"official technical documentation RFC {topic}"
        res_summary = search_fn(search_query)
        
        research_entry = {
            "source": "Google Search Engine API",
            "topic": topic,
            "summary": res_summary,
            "confidence": 0.88,
            "isolated": True
        }
        
        self.external_docs.append(research_entry)
        
        return {
            "status": "RESEARCH_COMPLETED",
            "findings_count": 1,
            "isolated_entry": research_entry
        }
