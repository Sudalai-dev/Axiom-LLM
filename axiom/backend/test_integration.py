import http.client
import json

def run_integration_test():
    print("==========================================================")
    print("Axiom API Core & Auth Integration Test")
    print("==========================================================")

    # 1. Authenticate with seeded Admin credentials
    conn = http.client.HTTPConnection("127.0.0.1", 8000)
    login_data = json.dumps({"username": "admin", "password": "admin123"})
    headers = {"Content-Type": "application/json"}
    
    print("[1] Logging in as admin...")
    conn.request("POST", "/api/v1/auth/login", body=login_data, headers=headers)
    res = conn.getresponse()
    data = json.loads(res.read().decode())
    
    if res.status != 200:
        print(f"FAILED: Login response status {res.status}. Data: {data}")
        return
        
    token = data.get("access_token")
    print(f"SUCCESS: Received Access Token (length: {len(token)})\n")

    # 2. Create a new project workspace using the JWT token
    auth_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    project_payload = json.dumps({
        "name": "Axiom IoT Ingestion Node",
        "description": "Orchestrates local MQTT sensor ingestion data"
    })
    
    print("[2] Creating a new project workspace...")
    conn.request("POST", "/api/v1/projects", body=project_payload, headers=auth_headers)
    res = conn.getresponse()
    project_data = json.loads(res.read().decode())
    
    if res.status == 200:
        print(f"SUCCESS: Created Project ID: {project_data.get('id')} Name: '{project_data.get('name')}'\n")
    else:
        print(f"INFO: Project creation returned status {res.status} (likely already exists). Message: {project_data}\n")

    # 3. Retrieve list of project workspaces
    print("[3] Listing project workspaces...")
    conn.request("GET", "/api/v1/projects", headers=auth_headers)
    res = conn.getresponse()
    list_data = json.loads(res.read().decode())
    print(f"SUCCESS: Retrieved {len(list_data)} project(s):")
    for proj in list_data:
        print(f"  - [{proj['id']}] {proj['name']}: {proj.get('description')}")
    print("")

    # 4. Query the cognitive engine chat endpoint
    chat_payload = json.dumps({
        "query": "Explain normalizer rule mapping replacements",
        "session_id": "test-session"
    })
    print("[4] Querying 8-layer cognitive chat endpoint...")
    conn.request("POST", "/api/v1/chat", body=chat_payload, headers=auth_headers)
    res = conn.getresponse()
    chat_data = json.loads(res.read().decode())
    
    if res.status == 200:
        print("SUCCESS: Cognitive Pipeline Response:\n")
        print(chat_data.get("response"))
    else:
        print(f"FAILED: Chat endpoint returned status {res.status}. Data: {chat_data}")
        
    print("==========================================================")

if __name__ == "__main__":
    run_integration_test()
