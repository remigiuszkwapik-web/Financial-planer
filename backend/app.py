"""FastAPI app: serves the API and the local web frontend.

Run locally with:  uvicorn backend.app:app --reload
Everything stays on your machine — no external calls, no AI. The only "smart"
step is OCR reading numbers off a screenshot; all money logic is deterministic.
"""

from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import analysis, dates, db, ocr
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


class AssignIn(BaseModel):
    category_id: int


class BalanceIn(BaseModel):
    target_cents: int


# ---- helpers ----------------------------------------------------------------

def build_overview() -> dict:
    cats = db.list_categories()
    txs = db.list_all_transactions()
    totals = {t["name"]: t for t in analysis.category_totals(txs)}
    cat_out = []
    for c in cats:
        t = totals.get(c["name"], {"total_cents": 0, "count": 0})
        cat_out.append({
            "id": c["id"], "name": c["name"], "position": c["position"],
            "total_cents": t["total_cents"], "count": t["count"],
        })
    return {
        "balance_cents": db.balance_cents(),
        "start_balance_cents": db.get_start_balance_cents(),
        "unsorted": db.list_unsorted_expenses(),
        "categories": cat_out,
    }


# ---- meta -------------------------------------------------------------------

@app.get("/api/status")
def status() -> dict:
    return {"ocr_available": ocr.ocr_available()}


@app.get("/api/overview")
def overview() -> dict:
    return build_overview()


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


@app.get("/api/categories/{category_id}/items")
def category_items(category_id: int) -> list[dict]:
    return db.list_by_category(category_id)


# ---- transactions / cards ---------------------------------------------------

@app.post("/api/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    data = await file.read()
    if not data:
        raise HTTPException(400, "Leere Datei")

    suffix = Path(file.filename or "").suffix or ".png"
    fname = f"{int(time.time() * 1000)}{suffix}"
    (UPLOAD_DIR / fname).write_bytes(data)

    result = ocr.extract(data)
    created = 0
    for row in result["transactions"]:
        amount = row["amount_cents"]
        db.add_transaction(
            amount, row["payee"],
            kind="income" if amount > 0 else "expense",
            occurred_on=dates.parse_label(row.get("date_label")),
            image_path=fname,
        )
        created += 1

    if created == 0:
        # OCR found nothing (or is unavailable) — one blank expense card so the
        # user can type it in by hand.
        db.add_transaction(0, None, kind="expense", image_path=fname)

    return build_overview()


@app.post("/api/cards")
def add_blank_card() -> dict:
    return db.add_transaction(0, None, kind="expense")


@app.patch("/api/transactions/{tx_id}")
def patch_transaction(tx_id: int, body: TransactionUpdate) -> dict:
    tx = db.update_transaction(tx_id, amount_cents=body.amount_cents, payee=body.payee)
    if tx is None:
        raise HTTPException(404, "Buchung nicht gefunden")
    return tx


@app.post("/api/transactions/{tx_id}/assign")
def assign_transaction(tx_id: int, body: AssignIn) -> dict:
    tx = db.set_category(tx_id, body.category_id)
    if tx is None:
        raise HTTPException(404, "Buchung nicht gefunden")
    return tx


@app.post("/api/transactions/{tx_id}/unassign")
def unassign_transaction(tx_id: int) -> dict:
    tx = db.set_category(tx_id, None)
    if tx is None:
        raise HTTPException(404, "Buchung nicht gefunden")
    return tx


@app.delete("/api/transactions/{tx_id}")
def remove_transaction(tx_id: int) -> dict:
    db.delete_transaction(tx_id)
    return {"ok": True}


# ---- balance ----------------------------------------------------------------

@app.get("/api/balance")
def get_balance() -> dict:
    return {
        "balance_cents": db.balance_cents(),
        "start_balance_cents": db.get_start_balance_cents(),
    }


@app.put("/api/balance")
def set_balance(body: BalanceIn) -> dict:
    # Set the displayed balance to the target by adjusting the starting value,
    # so it stays consistent with the tracked transactions.
    db.set_start_balance_cents(db.get_start_balance_cents() + (body.target_cents - db.balance_cents()))
    return {"balance_cents": db.balance_cents()}


# ---- analysis ---------------------------------------------------------------

@app.get("/api/analysis")
def get_analysis() -> dict:
    return analysis.monthly_report(db.list_all_transactions())


# ---- export -----------------------------------------------------------------

@app.get("/api/export/markdown")
def export_md() -> Response:
    content = to_markdown(db.list_all_transactions(), balance_cents=db.balance_cents())
    return Response(content, media_type="text/markdown",
                    headers={"Content-Disposition": "attachment; filename=finanzen.md"})


@app.get("/api/export/xlsx")
def export_xlsx() -> Response:
    content = to_xlsx(db.list_all_transactions(), balance_cents=db.balance_cents())
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=finanzen.xlsx"},
    )


@app.get("/api/image/{fname}")
def image(fname: str) -> FileResponse:
    path = UPLOAD_DIR / Path(fname).name
    if not path.exists():
        raise HTTPException(404, "Bild nicht gefunden")
    return FileResponse(path)


# ---- frontend ---------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse((FRONTEND_DIR / "index.html").read_text(encoding="utf-8"))


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
