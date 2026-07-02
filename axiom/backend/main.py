import os
import sys

# Ensure the project root directory is in sys.path for module resolution
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import uvicorn
from fastapi import FastAPI
from axiom.backend.api.router import router
from axiom.storage.database import engine, Base, SessionLocal
from axiom.storage import models
from axiom.auth import manager

# Create all database tables locally on startup
Base.metadata.create_all(bind=engine)

# Seed initial roles and default admin user if database is empty
def seed_database():
    db = SessionLocal()
    try:
        # Check if roles are populated
        if not db.query(models.Role).first():
            admin_role = models.Role(name="Admin", description="Platform Administrator")
            dev_role = models.Role(name="Developer", description="Platform Developer")
            viewer_role = models.Role(name="Viewer", description="Read-only Viewer")
            db.add_all([admin_role, dev_role, viewer_role])
            db.commit()
            print("Seeded roles: Admin, Developer, Viewer")

        # Check if admin user is populated
        if not db.query(models.User).first():
            admin_role = db.query(models.Role).filter(models.Role.name == "Admin").first()
            default_admin = models.User(
                username="admin",
                hashed_password=manager.hash_password("admin123"),  # Safe local credentials
                role_id=admin_role.id,
                is_active=True
            )
            db.add(default_admin)
            db.commit()
            print("Seeded default admin user: 'admin' (password: 'admin123')")
    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

seed_database()

app = FastAPI(title="Axiom AI-Driven Inference IoT Orchestration Model API")

# Include core system API routes
app.include_router(router)

from fastapi.staticfiles import StaticFiles
import os

# Mount frontend static files
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

if __name__ == "__main__":
    # Local-first direct test run
    uvicorn.run("axiom.backend.main:app", host="127.0.0.1", port=8000, reload=True)
