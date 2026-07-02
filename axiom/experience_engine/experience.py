from typing import Dict, Any, List

class ExperienceEngine:
    """
    ExperienceEngine: Packages final execution results into interactive formats 
    (Markdown, Mermaid, swagger specs) for console presentation.
    """
    def __init__(self):
        pass

    def render(self, reasoning_trace: str, agent_results: List[Dict[str, Any]], execution_logs: Dict[str, Any]) -> str:
        paragraphs = [
            "# Axiom OS Technical Output Report",
            f"### Reasoning Execution Trace\n{reasoning_trace}",
            "### Execution Verification Sandbox Logs",
            "**Execution Status**: `{}`".format(execution_logs.get('status')),
            "**Stdout Logs**:\n```\n{}\n```".format(execution_logs.get('stdout') or '[Empty]')
        ]
        
        if execution_logs.get("error"):
            paragraphs.append(f"> [!CAUTION]\n> Execution error detected: {execution_logs.get('error')}")

        paragraphs.append("### Collaborative Agent Artifacts")
        for res in agent_results:
            agent_name = res.get("agent", "UnknownAgent")
            art = res.get("artifacts", {})
            lang = art.get("type", "text")
            content = art.get("content", "")
            paragraphs.append(
                f"**Agent**: `{agent_name}` | Confidence: `{res.get('confidence')}`\n"
                f"```{lang}\n{content}\n```"
            )
            
        return "\n\n".join(paragraphs)
