from __future__ import annotations
from backend.database import SessionLocal
from backend.llm.deepseek import get_llm
from backend.graph.orchestrator import get_orchestrator


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
