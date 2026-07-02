from axiom.knowledge_engine.engine import KnowledgeEngine
import os

def run_knowledge_integration_test():
    print("==========================================================")
    print("Axiom Knowledge Platform & Engines Integration Test")
    print("==========================================================")

    # Initialize the core KnowledgeEngine
    ke = KnowledgeEngine()

    # Define test file path
    test_filepath = os.path.join("D:\\Tasks\\Axiom - LLM", "Axiom_AI-Driven_Inference_IoT_Orchestration_Model.md")
    project_id = 1

    print(f"[1] Ingesting source file: {test_filepath}...")
    ingest_result = ke.ingest_document(test_filepath, project_id)
    print(f"SUCCESS: Ingestion finished. Result: {ingest_result}\n")

    # Perform a hybrid semantic vector-graph query
    test_query = "What is the cognitive operating system for AIoT?"
    print(f"[2] Executing search query: '{test_query}'...")
    search_results = ke.search_knowledge(test_query, project_id, limit=3)
    
    print(f"SUCCESS: Retrieved {len(search_results)} search match(es):\n")
    for idx, res in enumerate(search_results):
        print(f"Match #{idx+1} (Source: {res['source']}, Heading: '{res['heading']}', Similarity: {res['score']:.4f})")
        print(f"Text Snippet:\n\"\"\"\n{res['text']}\n\"\"\"")
        if res.get("knowledge_graph_relationships"):
            print("Extracted Graph Relationship Triple(s):")
            for rel in res["knowledge_graph_relationships"]:
                print(f"  - {rel}")
        else:
            print("No graph relationships captured for matching keywords in this chunk.")
        print("-" * 50)
    print("==========================================================")

if __name__ == "__main__":
    run_knowledge_integration_test()
