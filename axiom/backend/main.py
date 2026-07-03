"""
OCIF Platform Entrypoint — Main Application Launcher.

Initializes database tables, executes seeds (default tenants, user roles, policies),
configures the API Gateway, and launches the server reload runtime.

Traces to:
  - Document 8 (System Architecture) Section 2: Component Layout
  - Document 20 (Coding Prompts) Section 3: Database seeding
"""

import json
import os
import sys
from datetime import date
from sqlalchemy import text


# Ensure the project root directory is in sys.path for module resolution
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import uvicorn
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from axiom.core.config import settings
from axiom.core.security import hash_password
from axiom.gateway.app import create_gateway_app
from axiom.layer8_experience.router import router as public_router
from axiom.storage.database import sync_engine, Base, SessionLocal
from axiom.storage import models


def bootstrap_database():
    """Creates database schema tables on startup if missing."""
    print("Executing database schema initialization...")
    Base.metadata.create_all(bind=sync_engine)
    print("Database schema loaded successfully.")


def seed_platform_data():
    """
    Seeds essential operational metadata:
    - Default tenant (UUID: 11111111-1111-1111-1111-111111111111)
    - Admin, Process Owner, Compliance, and End User profiles
    - Default policy rules (Rules-As-Code DSL)
    - Default mock Tools in registry
    """
    db = SessionLocal()
    try:
        tenant_id = "11111111-1111-1111-1111-111111111111"
        
        # 1. Seed Tenant
        tenant = db.query(models.Tenant).filter(models.Tenant.tenant_id == tenant_id).first()
        if not tenant:
            tenant = models.Tenant(
                tenant_id=tenant_id,
                name="Axiom Enterprise Inc",
                industry="IoT Systems & Robotics",
                isolation_mode="shared"
            )
            db.add(tenant)
            db.commit()
            print(f"Seeded tenant: {tenant.name} ({tenant_id})")

        # 2. Seed Users per RBAC Role (Doc 14 Section 3.1)
        user_seeds = [
            ("11111111-1111-1111-1111-222222222222", "admin_user", "platform_admin", "admin@axiom.com"),
            ("11111111-1111-1111-1111-333333333333", "process_owner_user", "process_owner", "owner@axiom.com"),
            ("11111111-1111-1111-1111-444444444444", "compliance_user", "compliance_officer", "compliance@axiom.com"),
            ("11111111-1111-1111-1111-555555555555", "operator_user", "end_user", "user@axiom.com"),
        ]
        
        for user_uuid, username, role, email in user_seeds:
            existing_user = db.query(models.User).filter(
                models.User.tenant_id == tenant_id,
                models.User.external_idp_subject == username
            ).first()
            
            if not existing_user:
                db_user = models.User(
                    user_id=user_uuid,
                    tenant_id=tenant_id,
                    external_idp_subject=username,
                    email=email,
                    role=role,
                    department="Engineering"
                )
                db.add(db_user)
                db.commit()
                print(f"Seeded RBAC User: '{username}' with role '{role}' ({user_uuid})")

        # 3. Seed Default Allow Policies (Doc 14 Section 6)
        policy_name = "default-financial-limits-policy"
        policy = db.query(models.Policy).filter(
            models.Policy.tenant_id == tenant_id,
            models.Policy.name == policy_name
        ).first()
        
        if not policy:
            # Policy DSL: allow refund tools if amount <= 500.0
            rule_def = {
                "rules": [
                    {
                        "field": "amount",
                        "operator": "lte",
                        "value": 500.0,
                        "effect": "allow"
                    }
                ]
            }
            db_policy = models.Policy(
                tenant_id=tenant_id,
                name=policy_name,
                rule_definition=json.dumps(rule_def),
                risk_threshold=0.700,
                is_active=True
            )
            db.add(db_policy)
            db.commit()
            print(f"Seeded RLS policy: {policy_name}")

        # 4. Seed Default Mock Tools (Doc 9 Section 4.4)
        tool_name = "code_generator_tool"
        tool = db.query(models.Tool).filter(
            models.Tool.tenant_id == tenant_id,
            models.Tool.name == tool_name
        ).first()
        
        if not tool:
            input_sch = {
                "type": "object",
                "properties": {
                    "language": {"type": "string"},
                    "framework": {"type": "string"}
                },
                "required": ["language"]
            }
            output_sch = {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "content": {"type": "string"}
                }
            }
            
            db_tool = models.Tool(
                tenant_id=tenant_id,
                name=tool_name,
                description="Generates standard code templates for developer sessions",
                input_schema=json.dumps(input_sch),
                output_schema=json.dumps(output_sch),
                risk_level="low",
                requires_approval=False,
                endpoint="local",
                is_active=True
            )
            db.add(db_tool)
            db.commit()
            print(f"Seeded tool registry: '{tool_name}'")

        # 5. Seed Dashboard metrics (Doc 9 Section 4.6)
        today = date.today()
        metric = db.query(models.UsageMetric).filter(
            models.UsageMetric.tenant_id == tenant_id,
            models.UsageMetric.metric_date == today
        ).first()
        if not metric:
            db_metric = models.UsageMetric(
                tenant_id=tenant_id,
                metric_date=today,
                token_count=1250,
                request_count=12,
                automation_count=10,
                cost_usd=0.035
            )
            db.add(db_metric)
            db.commit()
            print("Seeded daily dashboard metrics.")

    except Exception as e:
        print(f"Failed database bootstrap seeding: {e}")
        db.rollback()
    finally:
        db.close()


bootstrap_database()
seed_platform_data()

# Launch API Gateway App
app = create_gateway_app()

# Mount Layer 8 Routers
app.include_router(public_router)

# Mount frontend static folders if present
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir, html=True), name="frontend")

# Redirect root to the mounted frontend for convenience
@app.get("/", include_in_schema=False)
async def _root():
    return RedirectResponse(url="/static/")

if __name__ == "__main__":
    uvicorn.run("axiom.backend.main:app", host="127.0.0.1", port=8000, reload=True)
