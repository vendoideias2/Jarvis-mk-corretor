"""
~/nexora/server/missions.py — Gerenciador de Missões e Kanban do NEXORA 3.0.
"""

import json
import time
import store

_SCHEMA = """
CREATE TABLE IF NOT EXISTS missions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    assigned_agent TEXT NOT NULL,
    status TEXT NOT NULL, -- backlog, planning, approval_needed, in_progress, done
    plan TEXT,
    result TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
"""

store.ensure(_SCHEMA, "missions")


def register(route, ApiError):
    @route("GET", "/api/missions")
    def handle_list_missions(req, query, body):
        missions = store.query("SELECT * FROM missions ORDER BY updated_at DESC")
        return {"ok": True, "missions": missions}

    @route("POST", "/api/missions")
    def handle_create_mission(req, query, body):
        if not body:
            raise ApiError(400, "Dados da missão obrigatórios")
        
        mid = f"mis_{int(time.time() * 1000)}"
        title = body.get("title", "").strip()
        description = body.get("description", "").strip()
        assigned = body.get("assigned_agent", "executor").lower()
        status = body.get("status", "backlog")
        plan = body.get("plan", "")
        
        if not title:
            raise ApiError(400, "Título da missão é obrigatório")

        now = time.time()
        store.execute(
            "INSERT INTO missions (id, title, description, assigned_agent, status, plan, result, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (mid, title, description, assigned, status, plan, "", now, now)
        )
        return {"ok": True, "id": mid, "title": title, "status": status}

    @route("POST", "/api/missions/move")
    def handle_move_mission(req, query, body):
        if not body:
            raise ApiError(400, "Dados obrigatórios")
        mid = body.get("id")
        new_status = body.get("status")
        if not mid or not new_status:
            raise ApiError(400, "ID e novo status são obrigatórios")
        
        now = time.time()
        store.execute(
            "UPDATE missions SET status = ?, updated_at = ? WHERE id = ?",
            (new_status, now, mid)
        )
        return {"ok": True, "id": mid, "status": new_status}

    @route("POST", "/api/missions/approve")
    def handle_approve_mission(req, query, body):
        if not body:
            raise ApiError(400, "Dados obrigatórios")
        mid = body.get("id")
        if not mid:
            raise ApiError(400, "ID da missão é obrigatório")
        
        now = time.time()
        store.execute(
            "UPDATE missions SET status = 'in_progress', updated_at = ? WHERE id = ?",
            (now, mid)
        )
        return {"ok": True, "id": mid, "status": "in_progress", "message": "Missão aprovada para execução!"}
