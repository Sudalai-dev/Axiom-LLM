import http.client
import json

def run_advanced_test():
    print("==========================================================")
    print("Axiom Advanced Cognitive Engines & Endpoints Test")
    print("==========================================================")

    # 1. Login to get JWT
    conn = http.client.HTTPConnection("127.0.0.1", 8000)
    login_data = json.dumps({"username": "admin", "password": "admin123"})
    headers = {"Content-Type": "application/json"}
    
    conn.request("POST", "/api/v1/auth/login", body=login_data, headers=headers)
    res = conn.getresponse()
    data = json.loads(res.read().decode())
    token = data.get("access_token")
    
    auth_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    # 2. Test NLP & Intent Analysis Endpoint
    nlp_payload = json.dumps({"query": "Generate local FastAPI schema for MQTT logs"})
    print("[1] Querying /nlp/analyze (NLP & Multi-Stage Intent Engine)...")
    conn.request("POST", "/api/v1/nlp/analyze", body=nlp_payload, headers=auth_headers)
    res = conn.getresponse()
    nlp_data = json.loads(res.read().decode())
    print("SUCCESS: NLP Analysis:")
    print(json.dumps(nlp_data.get("nlp_analysis"), indent=2))
    print("SUCCESS: Intent Stages Graph:")
    for stage in nlp_data.get("intent_graph", {}).get("stages", []):
        print(f"  - {stage}")
    print(f"  - Combined Intent Confidence: {nlp_data.get('intent_graph', {}).get('confidence_score'):.2f}\n")

    # 3. Test Feedback Logging & controlled dataset candidate creation
    feedback_payload = json.dumps({
        "query": "Validate broker config",
        "response": "Broker config valid.",
        "score": 1,  # Low score triggers training candidate
        "comments": "Failed to check TLS version settings."
    })
    print("[2] Logging negative feedback to /feedback...")
    conn.request("POST", "/api/v1/feedback", body=feedback_payload, headers=auth_headers)
    res = conn.getresponse()
    feedback_data = json.loads(res.read().decode())
    print(f"SUCCESS: Feedback logged. ID: {feedback_data.get('feedback_id')}\n")

    # 4. List pending training candidates (Admin check)
    print("[3] Fetching pending training dataset candidates...")
    conn.request("GET", "/api/v1/training/candidates", headers=auth_headers)
    res = conn.getresponse()
    candidates = json.loads(res.read().decode())
    print(f"SUCCESS: Found {len(candidates)} pending dataset candidates:")
    candidate_id = ""
    for c in candidates:
        candidate_id = c["candidate_id"]
        print(f"  - [{c['candidate_id']}] Prompt: '{c['input_prompt']}' -> Correction: '{c['target_corrected_output']}'")
    print("")

    # 5. Approve dataset candidate for controlled offline fine-tuning
    if candidate_id:
        approve_payload = json.dumps({"candidate_id": candidate_id})
        print(f"[4] Approving candidate [{candidate_id}] for training dataset...")
        conn.request("POST", "/api/v1/training/approve", body=approve_payload, headers=auth_headers)
        res = conn.getresponse()
        approve_data = json.loads(res.read().decode())
        print(f"SUCCESS: Candidate approved. Status: {approve_data.get('status')}\n")

    # 6. Retrieve active model profile from Model Registry
    print("[5] Querying /models/active...")
    conn.request("GET", "/api/v1/models/active", headers=auth_headers)
    res = conn.getresponse()
    model_data = json.loads(res.read().decode())
    print(f"SUCCESS: Active model name: '{model_data.get('model_name')}' reliability rating: {model_data.get('reliability_rating')}\n")

    # 7. Switch active model profile
    switch_payload = json.dumps({"model_name": "llama3.1-8b"})
    print("[6] Switching active inference model to 'llama3.1-8b'...")
    conn.request("POST", "/api/v1/models/switch", body=switch_payload, headers=auth_headers)
    res = conn.getresponse()
    switch_data = json.loads(res.read().decode())
    print(f"SUCCESS: Model swapped. Status: {switch_data.get('status')} Active Model: {switch_data.get('active_model')}\n")

    # 8. Re-query active model to verify
    conn.request("GET", "/api/v1/models/active", headers=auth_headers)
    res = conn.getresponse()
    model_data = json.loads(res.read().decode())
    print(f"SUCCESS: Current Active model name: '{model_data.get('model_name')}'\n")

    print("==========================================================")

if __name__ == "__main__":
    run_advanced_test()
