"""FastAPI app: serves the API and the local web frontend.

Run locally with:  uvicorn backend.app:app --reload
Everything stays on your machine — no external calls, no AI.
"""

from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db, ocr
from .export import to_markdown, to_xlsx

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
UPLOAD_DIR = BASE_DIR / "data" / "uploads"

app = FastAPI(title="Financial Planer")


@app.on_event("startup")
def _startup() -> None:
    db.init_db()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ---- models -----------------------------------------------------------------

class CategoryIn(BaseModel):
    name: str


class TransactionUpdate(BaseModel):
    amount_cents: int | None = None
    payee: str | None = None
    category_id: int | None = None
    set_category: bool = False


# ---- meta -------------------------------------------------------------------

@app.get("/api/status")
def status() -> dict:
    return {"ocr_available": ocr.ocr_available()}


# ---- categories -------------------------------------------------------------

@app.get("/api/categories")
def get_categories() -> list[dict]:
    return db.list_categories()


@app.post("/api/categories")
def create_category(body: CategoryIn) -> dict:
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Name darf nicht leer sein")
    try:
        return db.add_category(name)
    except Exception:
        raise HTTPException(409, "Kategorie existiert bereits")


@app.delete("/api/categories/{category_id}")
def remove_category(category_id: int) -> dict:
    db.delete_category(category_id)
    return {"ok": True}


# ---- transactions / cards ---------------------------------------------------

@app.post("/api/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    data = await file.read()
    if not data:
        raise HTTPException(400, "Leere Datei")

    # Persist the screenshot so the card can show a preview.
    suffix = Path(file.filename or "").suffix or ".png"
    fname = f"{int(time.time() * 1000)}{suffix}"
    (UPLOAD_DIR / fname).write_bytes(data)

    result = ocr.extract(data)
    tx = db.add_transaction(
        amount_cents=result["amount_cents"] or 0,
        payee=result["payee"],
        raw_text=result["raw_text"],
        image_path=fname,
    )
    return tx


@app.get("/api/cards")
def cards() -> list[dict]:
    return db.list_unsorted()


@app.patch("/api/transactions/{tx_id}")
def patch_transaction(tx_id: int, body: TransactionUpdate) -> dict:
    tx = db.update_transaction(
        tx_id,
        amount_cents=body.amount_cents,
        payee=body.payee,
        category_id=body.category_id,
        set_category=body.set_category,
    )
    if tx is None:
        raise HTTPException(404, "Buchung nicht gefunden")
    return tx


@app.delete("/api/transactions/{tx_id}")
def remove_transaction(tx_id: int) -> dict:
    db.delete_transaction(tx_id)
    return {"ok": True}


@app.get("/api/image/{fname}")
def image(fname: str) -> FileResponse:
    path = UPLOAD_DIR / Path(fname).name
    if not path.exists():
        raise HTTPException(404, "Bild nicht gefunden")
    return FileResponse(path)


# ---- summary / export -------------------------------------------------------

@app.get("/api/summary")
def summary() -> dict:
    from .calc import summarize

    return summarize(db.list_all_transactions())


@app.get("/api/export/markdown")
def export_md() -> Response:
    content = to_markdown(db.list_all_transactions())
    return Response(
        content,
        media_type="text/markdown",
        headers={"Content-Disposition": "attachment; filename=finanzen.md"},
    )


@app.get("/api/export/xlsx")
def export_xlsx() -> Response:
    content = to_xlsx(db.list_all_transactions())
    return Response(
        content,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={"Content-Disposition": "attachment; filename=finanzen.xlsx"},
    )


# ---- frontend ---------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse((FRONTEND_DIR / "index.html").read_text(encoding="utf-8"))


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
