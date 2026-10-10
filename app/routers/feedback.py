import secrets

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.feedback import Feedback
from app.models.user import User
from app.timezone import to_nepal_time
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[2] / "templates"))

CATEGORIES = {
    "ai_teacher": "AI teacher",
    "lesson": "Lessons",
    "bug": "Bug report",
    "idea": "Feature idea",
    "other": "Other",
}


@router.get("/feedback")
async def feedback_page(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=303)
    user = db.get(User, user_id)
    if not user:
        request.session.clear()
        return RedirectResponse("/login", status_code=303)

    csrf_token = request.session.get("feedback_csrf")
    if not csrf_token:
        csrf_token = secrets.token_urlsafe(32)
        request.session["feedback_csrf"] = csrf_token
    existing = (
        db.query(Feedback)
        .filter(Feedback.user_id == user.id)
        .order_by(Feedback.created_at.desc(), Feedback.id.desc())
        .first()
    )
    return templates.TemplateResponse(
        request=request,
        name="feedback.html",
        context={
            "user": user,
            "existing": existing,
            "categories": CATEGORIES,
            "csrf_token": csrf_token,
            "to_nepal_time": to_nepal_time,
        },
    )


@router.post("/api/feedback")
async def submit_feedback(
    request: Request,
    category: str = Form(...),
    rating: int = Form(...),
    message: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse({"ok": False, "error": "Please log in to send feedback."}, status_code=401)
    user = db.get(User, user_id)
    if not user:
        request.session.clear()
        return JSONResponse({"ok": False, "error": "Account not found. Please log in again."}, status_code=401)
    expected_token = request.session.get("feedback_csrf", "")
    if not expected_token or not secrets.compare_digest(csrf_token, expected_token):
        return JSONResponse({"ok": False, "error": "This form expired. Refresh the page and try again."}, status_code=403)

    message = message.strip()
    if category not in CATEGORIES:
        return JSONResponse({"ok": False, "error": "Choose a valid feedback category."}, status_code=400)
    if rating not in range(1, 6):
        return JSONResponse({"ok": False, "error": "Choose a rating from 1 to 5 stars."}, status_code=400)
    if len(message) < 10 or len(message) > 2000:
        return JSONResponse({"ok": False, "error": "Feedback must be between 10 and 2,000 characters."}, status_code=400)

    entry = (
        db.query(Feedback)
        .filter(Feedback.user_id == user.id)
        .order_by(Feedback.created_at.desc(), Feedback.id.desc())
        .first()
    )
    updated = entry is not None
    if entry is None:
        entry = Feedback(user_id=user.id, category=category, rating=rating, message=message)
        db.add(entry)
    else:
        entry.category = category
        entry.rating = rating
        entry.message = message
    db.commit()
    db.refresh(entry)
    created_at = to_nepal_time(entry.created_at)
    return JSONResponse({"ok": True, "id": entry.id, "updated": updated, "created_at": created_at.strftime("%b %d, %Y at %H:%M Nepal Time")})
