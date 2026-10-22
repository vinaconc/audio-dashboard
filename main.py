import json
import re
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import text, func
from sqlalchemy.orm import Session
from db import get_db
from models import Job
from pydantic import BaseModel
app = FastAPI(title="Chord Analyzer — Dashboard")


@app.get("/api/stats")
def stats(db: Session = Depends(get_db)):
    by_status = dict(
        db.query(Job.status, func.count(Job.id)).group_by(Job.status).all()
    )
    total = sum(by_status.values())
    avg_dur = db.execute(text("""
        SELECT AVG(EXTRACT(EPOCH FROM (finished_at - started_at)))
        FROM jobs
        WHERE status = 'completed'
          AND started_at IS NOT NULL
          AND finished_at IS NOT NULL
          AND finished_at > NOW() - INTERVAL '7 days'
    """)).scalar() or 0
    return {
        "total": total,
        "by_status": by_status,
        "avg_duration_seconds": round(avg_dur, 1),
    }


@app.get("/api/jobs/list")
def jobs_list(
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(Job)
    if status:
        q = q.filter(Job.status == status)
    total = q.count()
    rows = q.order_by(Job.id.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "id": j.id,
                "title": j.title,
                "original_filename": j.original_filename,
                "url": j.url,
                "status": j.status,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "started_at": j.started_at.isoformat() if j.started_at else None,
                "finished_at": j.finished_at.isoformat() if j.finished_at else None,
                "duration_seconds": (
                    (j.finished_at - j.started_at).total_seconds()
                    if j.started_at and j.finished_at else None
                ),
            }
            for j in rows
        ],
    }


@app.get("/api/jobs/{job_id}/detail")
def job_detail(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")

    result_parsed = None
    if job.result:
        try:
            result_parsed = json.loads(job.result)
        except Exception:
            result_parsed = {"_raw": job.result[:1000], "_parse_error": True}

    return {
        "id": job.id,
        "title": job.title,
        "original_filename": job.original_filename,
        "url": job.url,
        "status": job.status,
        "lyrics": job.lyrics,
        "error": job.error,
        "result": result_parsed,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "duration_seconds": (
            (job.finished_at - job.started_at).total_seconds()
            if job.started_at and job.finished_at else None
        ),
        "structure_user": job.structure_user,
    }


@app.post("/api/jobs/{job_id}/requeue")
def job_requeue(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")

    if job.status not in ("completed", "error"):
        raise HTTPException(
            status_code=400,
            detail=f"Solo se pueden reencolar jobs completed o error (actual: {job.status})",
        )

    job.status = "pending"
    job.error = None
    job.started_at = None
    job.finished_at = None
    db.commit()
    db.refresh(job)
    return {"ok": True, "id": job.id, "status": job.status}


@app.get("/api/workers/status")
def workers_status(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT worker_id, state, last_heartbeat,
               EXTRACT(EPOCH FROM (NOW() - last_heartbeat))
                   AS seconds_since_heartbeat
        FROM worker_status
        WHERE worker_id IN ('local-worker', 'kaggle-worker')
    """)).mappings().all()

    workers = {
        "local-worker": {
            "active": False,
            "state": "unknown",
            "last_heartbeat": None,
            "seconds_since_heartbeat": None,
        },
        "kaggle-worker": {
            "active": False,
            "state": "unknown",
            "last_heartbeat": None,
            "seconds_since_heartbeat": None,
        },
    }

    for row in rows:
        worker_id = row["worker_id"]
        state = row["state"]
        seconds = row["seconds_since_heartbeat"]
        heartbeat = row["last_heartbeat"]

        seconds = float(seconds) if seconds is not None else None
        active = (
            state == "running"
            and seconds is not None
            and seconds < 30
        )

        workers[worker_id] = {
            "active": active,
            "state": state,
            "last_heartbeat": (
                heartbeat.isoformat() if heartbeat is not None else None
            ),
            "seconds_since_heartbeat": seconds,
        }

    active_workers = [
        worker_id
        for worker_id, info in workers.items()
        if info["active"]
    ]

    return {
        "status": "ok",
        "active": bool(active_workers),
        "active_workers": active_workers,
        "workers": workers,
    }

@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return (Path(__file__).resolve().parent / "dashboard.html").read_text(encoding="utf-8")

# ============================================================
# ADMIN — Crear tablas dinámicamente
# ============================================================

import re
from pydantic import BaseModel


class ColumnDef(BaseModel):
    name: str
    type: str
    nullable: bool = True
    primary_key: bool = False
    default: str | None = None


class CreateTableRequest(BaseModel):
    table_name: str
    columns: list[ColumnDef]
    if_not_exists: bool = True


# Whitelist de tipos permitidos (evita SQL injection)
ALLOWED_TYPES = {
    "INTEGER", "BIGINT", "SMALLINT",
    "SERIAL", "BIGSERIAL", "SMALLSERIAL",
    "TEXT", "VARCHAR(255)", "VARCHAR(500)",
    "BOOLEAN",
    "REAL", "DOUBLE PRECISION", "NUMERIC",
    "DATE", "TIMESTAMP", "TIMESTAMPTZ",
    "JSONB", "JSON", "UUID",
}

# Whitelist de defaults permitidos
ALLOWED_DEFAULTS = {
    None, "", "NOW()", "CURRENT_TIMESTAMP", "CURRENT_DATE",
    "TRUE", "FALSE", "0", "1", "gen_random_uuid()",
    "'info'", "'pending'", "'completed'", "'error'",
}

IDENTIFIER_RE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def _validate_identifier(name: str, kind: str = "identificador") -> None:
    if not IDENTIFIER_RE.match(name):
        raise HTTPException(
            status_code=400,
            detail=f"{kind} inválido: '{name}'. "
                   f"Solo minúsculas, números y guión bajo, empezando con letra o guión bajo.",
        )


@app.get("/api/admin/tables")
def list_tables(db: Session = Depends(get_db)):
    """Lista todas las tablas del schema public."""
    rows = db.execute(text("""
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY tablename
    """)).scalars().all()
    return {"tables": rows}


@app.get("/api/admin/column-types")
def column_types():
    """Lista blanca de tipos y defaults permitidos."""
    return {
        "types": sorted(ALLOWED_TYPES),
        "defaults": sorted([d for d in ALLOWED_DEFAULTS if d]),
    }

@app.get("/api/jobs/{job_id}/events")
def job_events(job_id: int, after_id: int = 0, limit: int = 200,
               db: Session = Depends(get_db)):
    """Devuelve los eventos de un job. Con after_id solo los nuevos."""
    rows = db.execute(text("""
        SELECT id, ts, level, stage, message, data
        FROM job_events
        WHERE job_id = :j AND id > :after
        ORDER BY id ASC
        LIMIT :l
    """), {"j": job_id, "after": after_id, "l": limit}).mappings().all()
    return [dict(r) for r in rows]

@app.post("/api/admin/sql")
def admin_sql(payload: dict, db: Session = Depends(get_db)):
    sql = (payload.get("sql") or "").strip()

    if not sql:
        raise HTTPException(status_code=400, detail="SQL vacío")

    # Permitimos solamente SELECT y UPDATE.
    sql_normalized = sql.lstrip().lower()

    if not (
        sql_normalized.startswith("select ")
        or sql_normalized.startswith("select\n")
        or sql_normalized == "select"
        or sql_normalized.startswith("update ")
        or sql_normalized.startswith("update\n")
        or sql_normalized == "update"
    ):
        raise HTTPException(
            status_code=400,
            detail="Solo se permiten consultas SELECT y UPDATE"
        )

    # Una sola sentencia por ejecución.
    if ";" in sql_normalized.rstrip(";"):
        raise HTTPException(
            status_code=400,
            detail="Solo se permite una consulta SQL"
        )

    try:
        result = db.execute(text(sql))

        # SELECT
        if sql_normalized.startswith("select"):
            rows = result.mappings().all()

            return {
                "ok": True,
                "type": "select",
                "rows": [dict(row) for row in rows],
                "count": len(rows),
            }

        # UPDATE
        db.commit()

        return {
            "ok": True,
            "type": "update",
            "rows": [],
            "count": result.rowcount,
        }

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )



@app.post("/api/admin/create-table")
def create_table(req: CreateTableRequest, db: Session = Depends(get_db)):
    """Crea una tabla a partir de una definición validada."""
    _validate_identifier(req.table_name, "nombre de tabla")

    if not req.columns:
        raise HTTPException(status_code=400, detail="Debe haber al menos una columna")

    pks = sum(1 for c in req.columns if c.primary_key)
    if pks > 1:
        raise HTTPException(status_code=400, detail="Solo puede haber una PRIMARY KEY")

    seen = set()
    for col in req.columns:
        _validate_identifier(col.name, "nombre de columna")
        if col.name in seen:
            raise HTTPException(status_code=400, detail=f"Columna duplicada: {col.name}")
        seen.add(col.name)

        if col.type not in ALLOWED_TYPES:
            raise HTTPException(status_code=400, detail=f"Tipo no permitido: {col.type}")
        if col.default not in ALLOWED_DEFAULTS:
            raise HTTPException(status_code=400, detail=f"Default no permitido: {col.default}")

    # Construir DDL (todo viene de whitelist)
    lines = []
    for col in req.columns:
        parts = [col.name, col.type]
        if col.primary_key:
            parts.append("PRIMARY KEY")
        if not col.nullable and not col.primary_key:
            parts.append("NOT NULL")
        if col.default:
            parts.append(f"DEFAULT {col.default}")
        lines.append("    " + " ".join(parts))

    ine = "IF NOT EXISTS " if req.if_not_exists else ""
    ddl = f"CREATE TABLE {ine}{req.table_name} (\n" + ",\n".join(lines) + "\n);"

    try:
        db.execute(text(ddl))
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al crear tabla: {e}")

    return {"ok": True, "table": req.table_name, "ddl": ddl}