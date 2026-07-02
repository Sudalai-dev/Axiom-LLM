from fastapi import APIRouter, Depends, HTTPException, status, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session as DBSession
from typing import List, Dict, Any

from axiom.storage.database import get_db
from axiom.storage import models
from axiom.auth import manager
from axiom.cognitive_engine.pipeline import AxiomCognitivePipeline
from axiom.nlp_engine.nlp import NLPEngine
from axiom.intent_engine.intent import IntentEngine
from axiom.research_engine.research import ResearchEngine
from axiom.ai.registry import ModelRegistryEngine
from axiom.training.learning import LearningEngine

router = APIRouter(prefix="/api/v1")
pipeline = AxiomCognitivePipeline()
nlp_engine = NLPEngine()
intent_engine = IntentEngine()
research_engine = ResearchEngine()
model_registry = ModelRegistryEngine()
learning_engine = LearningEngine()

# API Token header extractor
token_header = APIKeyHeader(name="Authorization", auto_error=False)

def get_current_user(token: str = Depends(token_header), db: DBSession = Depends(get_db)) -> models.User:
    """Verifies the JWT token and returns the current user model."""
    if not token or not token.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Authorization header"
        )
    
    jwt_token = token.replace("Bearer ", "")
    payload = manager.decode_jwt_token(jwt_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
        
    username = payload.get("sub")
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    return user

def require_role(allowed_roles: List[str]):
    """Enforces role-based access controls (RBAC) on endpoints."""
    def dependency(user: models.User = Depends(get_current_user)):
        if user.role.name not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have sufficient permissions to perform this action"
            )
        return user
    return dependency

# Pydantic schemas for request validation
from pydantic import BaseModel

class LoginRequest(BaseModel):
    username: str
    password: str

class ProjectCreate(BaseModel):
    name: str
    description: str = None

class ChatRequest(BaseModel):
    query: str
    session_id: str = "default-session"

@router.post("/auth/login")
def login(req: LoginRequest, db: DBSession = Depends(get_db)):
    """User authentication and JWT token generation endpoint."""
    user = db.query(models.User).filter(models.User.username == req.username).first()
    if not user or not manager.verify_password(req.password, user.hashed_password):
        # Register audit log entry for failed attempt
        log = models.AuditLog(action="FAILED_LOGIN", details=f"Username: {req.username}")
        db.add(log)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    # Generate token containing username and role
    token_payload = {"sub": user.username, "role": user.role.name}
    token = manager.create_jwt_token(token_payload)
    
    # Log successful login
    log = models.AuditLog(user_id=user.id, action="SUCCESSFUL_LOGIN")
    db.add(log)
    db.commit()
    
    return {"access_token": token, "token_type": "bearer"}

@router.post("/projects", response_model=Dict[str, Any])
def create_project(
    project_in: ProjectCreate, 
    db: DBSession = Depends(get_db), 
    user: models.User = Depends(require_role(["Admin", "Developer"]))
):
    """Creates a new project context block (Admin and Developer role required)."""
    # Check if project name already exists
    existing = db.query(models.Project).filter(models.Project.name == project_in.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Project with this name already exists")
        
    project = models.Project(
        name=project_in.name,
        description=project_in.description,
        owner_id=user.id
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    
    # Log project creation
    log = models.AuditLog(user_id=user.id, action="PROJECT_CREATED", details=f"Project ID: {project.id}")
    db.add(log)
    db.commit()
    
    return {"id": project.id, "name": project.name, "description": project.description}

@router.get("/projects", response_model=List[Dict[str, Any]])
def list_projects(db: DBSession = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Lists all available projects (All authenticated roles can read)."""
    projects = db.query(models.Project).all()
    return [{"id": p.id, "name": p.name, "description": p.description} for p in projects]

@router.post("/chat")
def chat_endpoint(
    req: ChatRequest, 
    db: DBSession = Depends(get_db), 
    user: models.User = Depends(get_current_user)
):
    """Routes queries through the 8-layer cognitive pipeline engine."""
    try:
        result = pipeline.execute(req.query, session_id=req.session_id)
        if result.get("status") == "REJECTED":
            raise HTTPException(status_code=400, detail=result.get("rejection_reason"))
            
        # Log chat action
        log = models.AuditLog(user_id=user.id, action="COGNITIVE_CHAT_EXECUTION", details=f"Intent: {result.get('intent')}")
        db.add(log)
        db.commit()
        
        return {
            "status": result.get("status", "SUCCESS"),
            "intent": result.get("intent", "Unknown"),
            "response": result.get("experience_output", ""),
            "attempts": result.get("attempt", 1)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class FeedbackSubmit(BaseModel):
    query: str
    response: str
    score: int
    comments: str

class ResearchRequest(BaseModel):
    topic: str

class ModelSwitchRequest(BaseModel):
    model_name: str

class ApproveCandidateRequest(BaseModel):
    candidate_id: str

@router.post("/nlp/analyze")
def nlp_analyze(req: ChatRequest, user: models.User = Depends(get_current_user)):
    """Analyzes a raw text query, running NER, lemmatization and classification."""
    nlp_obj = nlp_engine.analyze(req.query)
    intent_graph = intent_engine.evaluate_intent(req.query, nlp_obj)
    return {
        "nlp_analysis": nlp_obj,
        "intent_graph": intent_graph
    }

@router.post("/research")
def trigger_research(req: ResearchRequest, user: models.User = Depends(require_role(["Admin", "Developer"]))):
    """Crawls trusted specifications online and isolates findings (Admin/Developer required)."""
    # Stub function calling Search Web Tool schema internally (mocked for REST stability)
    res_summary = f"Search result summary for online RFC on {req.topic}"
    
    result = research_engine.execute_online_research(req.topic, lambda q: res_summary)
    return result

@router.post("/feedback")
def submit_feedback(req: FeedbackSubmit, user: models.User = Depends(get_current_user)):
    """Logs user feedback and registers training dataset candidates if errors occurred."""
    feedback_id = learning_engine.collect_feedback(req.query, req.response, req.score, req.comments)
    return {"status": "LOGGED", "feedback_id": feedback_id}

@router.get("/training/candidates")
def get_candidates(user: models.User = Depends(require_role(["Admin"]))):
    """Lists pending dataset training candidates awaiting Admin approval."""
    return learning_engine.list_pending_candidates()

@router.post("/training/approve")
def approve_candidate(req: ApproveCandidateRequest, user: models.User = Depends(require_role(["Admin"]))):
    """Approves a candidate dataset profile for manual training queues (Admin required)."""
    success = learning_engine.approve_candidate(req.candidate_id)
    if not success:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return {"status": "APPROVED", "candidate_id": req.candidate_id}

@router.get("/models/active")
def get_active_model(user: models.User = Depends(get_current_user)):
    """Returns metadata profiles for the active local model runtime."""
    return model_registry.get_active_profile()

@router.post("/models/switch")
def switch_model(req: ModelSwitchRequest, user: models.User = Depends(require_role(["Admin"]))):
    """Swaps the active inference provider runtime settings (Admin required)."""
    success = model_registry.set_active_model(req.model_name)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid model name selection")
    return {"status": "SWAPPED", "active_model": req.model_name}
