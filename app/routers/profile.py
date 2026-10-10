import re

import bcrypt
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User

router = APIRouter()


def _current_user(request: Request, db: Session) -> User | None:
    user_id = request.session.get("user_id")
    return db.get(User, user_id) if user_id else None


@router.get("/api/profile/progress")
async def get_learning_progress(request: Request, db: Session = Depends(get_db)):
    user = _current_user(request, db)
    if not user:
        return JSONResponse({"ok": False, "error": "Please log in again."}, status_code=401)
    return JSONResponse({
        "ok": True,
        "level": user.learning_level,
        "submissions": user.code_submission_count,
        "last_result": user.last_review_result,
    })


@router.post("/api/profile/progress")
async def save_learning_progress(
    request: Request,
    level: str = Form(""),
    submissions: int = Form(0),
    last_result: str = Form(""),
    db: Session = Depends(get_db),
):
    user = _current_user(request, db)
    if not user:
        return JSONResponse({"ok": False, "error": "Please log in again."}, status_code=401)
    allowed_levels = {"", "Beginner", "Basic", "Intermediate", "Advanced", "Professional"}
    allowed_results = {"", "CORRECT", "PARTIAL", "INCORRECT"}
    if level not in allowed_levels or last_result not in allowed_results or submissions < 0:
        return JSONResponse({"ok": False, "error": "Invalid progress data."}, status_code=400)
    if level:
        user.learning_level = level
    user.code_submission_count = max(user.code_submission_count or 0, submissions)
    if last_result:
        user.last_review_result = last_result
    db.commit()
    return JSONResponse({"ok": True})


@router.post("/api/profile/update")
async def update_profile(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    username: str = Form(...),
    phone: str = Form(""),
    date_of_birth: str = Form(""),
    relationship_status: str = Form(""),
    location: str = Form(""),
    db: Session = Depends(get_db),
):
    user = _current_user(request, db)
    if not user:
        return JSONResponse({"ok": False, "error": "Please log in again."}, status_code=401)

    first_name, last_name = first_name.strip(), last_name.strip()
    username, phone, location = username.strip(), phone.strip(), location.strip()
    errors = []
    if not first_name or len(first_name) > 100:
        errors.append("First name is required and must be at most 100 characters.")
    if not last_name or len(last_name) > 100:
        errors.append("Last name is required and must be at most 100 characters.")
    if not re.fullmatch(r"[A-Za-z0-9_]{3,30}", username):
        errors.append("Username must be 3–30 characters and use only letters, numbers, or underscores.")
    if db.query(User).filter(User.username == username, User.id != user.id).first():
        errors.append("That username is already in use.")
    if len(phone) > 30 or (phone and len(re.sub(r"\D", "", phone)) < 7):
        errors.append("Enter a valid phone number.")
    if phone and db.query(User).filter(User.phone == phone, User.id != user.id).first():
        errors.append("That phone number is already in use.")
    if len(location) > 100:
        errors.append("Location must be at most 100 characters.")
    if len(relationship_status) > 50:
        errors.append("Relationship status must be at most 50 characters.")
    if len(date_of_birth) > 20:
        errors.append("Date of birth is invalid.")
    if errors:
        return JSONResponse({"ok": False, "error": " ".join(errors)}, status_code=400)

    user.first_name = first_name
    user.last_name = last_name
    user.username = username
    user.phone = phone
    user.date_of_birth = date_of_birth or None
    user.relationship_status = relationship_status.strip() or None
    user.location = location or None
    db.commit()
    request.session["username"] = username
    return JSONResponse({"ok": True, "username": username, "display_name": f"{first_name} {last_name}"})


@router.post("/api/profile/password")
async def update_password(
    request: Request,
    current_password: str = Form(""),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = _current_user(request, db)
    if not user:
        return JSONResponse({"ok": False, "error": "Please log in again."}, status_code=401)
    if user.auth_provider == "password":
        if len(current_password.encode()) > 72 or not bcrypt.checkpw(current_password.encode(), user.hashed_password.encode()):
            return JSONResponse({"ok": False, "error": "Current password is incorrect."}, status_code=400)
    if new_password != confirm_password:
        return JSONResponse({"ok": False, "error": "New passwords do not match."}, status_code=400)
    if len(new_password) < 8:
        return JSONResponse({"ok": False, "error": "New password must be at least 8 characters."}, status_code=400)
    if len(new_password.encode()) > 72:
        return JSONResponse({"ok": False, "error": "New password must be 72 bytes or fewer."}, status_code=400)

    user.hashed_password = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    user.auth_provider = "password"
    db.commit()
    return JSONResponse({"ok": True, "message": "Password changed successfully."})
