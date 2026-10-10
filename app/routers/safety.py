import secrets
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import ADMIN_EMAIL
from app.database import get_db
from app.models.direct_message import DirectMessage
from app.models.safety_report import SafetyReport
from app.models.user import User
from app.models.user_block import UserBlock
from app.models.user_follow import UserFollow
from app.timezone import to_nepal_time

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[2] / "templates"))
REPORT_REASONS = {
    "Harassment or bullying",
    "Spam or scam",
    "Inappropriate content",
    "Threats or safety concern",
    "Other",
}
REPORT_STATUSES = {"open", "in_review", "resolved", "dismissed"}


def _current_user(request: Request, db: Session) -> User | None:
    user_id = request.session.get("user_id")
    user = db.get(User, user_id) if user_id else None
    if user_id and not user:
        request.session.clear()
    return user


def _valid_csrf(request: Request, token: str) -> bool:
    expected = request.session.get("safety_csrf", "")
    return bool(expected and secrets.compare_digest(expected, token))


def _get_csrf(request: Request) -> str:
    token = request.session.get("safety_csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["safety_csrf"] = token
    return token


def _is_admin(user: User | None) -> bool:
    return bool(user and ADMIN_EMAIL and user.email.strip().lower() == ADMIN_EMAIL)


@router.get("/safety")
async def safety_page(request: Request, db: Session = Depends(get_db)):
    user = _current_user(request, db)
    blocked_users = []
    reports = []
    if user:
        blocked_users = (
            db.query(User)
            .join(UserBlock, UserBlock.blocked_id == User.id)
            .filter(UserBlock.blocker_id == user.id)
            .order_by(User.username.asc())
            .all()
        )
        reports = (
            db.query(SafetyReport)
            .filter(SafetyReport.reporter_id == user.id)
            .order_by(SafetyReport.created_at.desc(), SafetyReport.id.desc())
            .limit(50)
            .all()
        )
    return templates.TemplateResponse(
        request=request,
        name="safety.html",
        context={
            "user": user,
            "blocked_users": blocked_users,
            "reports": reports,
            "csrf_token": _get_csrf(request) if user else "",
            "is_admin": _is_admin(user),
            "to_nepal_time": to_nepal_time,
        },
    )


@router.get("/admin/safety-reports")
async def safety_reports_admin(request: Request, db: Session = Depends(get_db)):
    user = _current_user(request, db)
    if not _is_admin(user):
        return RedirectResponse("/safety", status_code=303)
    reports = db.query(SafetyReport).order_by(SafetyReport.created_at.desc(), SafetyReport.id.desc()).limit(300).all()
    rows = []
    for report in reports:
        reporter = db.get(User, report.reporter_id) if report.reporter_id else None
        target = db.get(User, report.reported_user_id) if report.reported_user_id else None
        rows.append({
            "report": report,
            "reporter_name": f"@{reporter.username}" if reporter else "Deleted account",
            "target_name": f"@{target.username}" if target else f"@{report.reported_username}",
            "message_excerpt": report.reported_message_excerpt,
        })
    return templates.TemplateResponse(
        request=request,
        name="safety_admin.html",
        context={"user": user, "reports": rows, "csrf_token": _get_csrf(request), "to_nepal_time": to_nepal_time},
    )


@router.post("/admin/safety-reports/{report_id}/status")
async def update_report_status(
    report_id: int,
    request: Request,
    status: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    user = _current_user(request, db)
    if not _is_admin(user):
        return RedirectResponse("/safety", status_code=303)
    if not _valid_csrf(request, csrf_token) or status not in REPORT_STATUSES:
        return RedirectResponse("/admin/safety-reports?error=invalid", status_code=303)
    report = db.get(SafetyReport, report_id)
    if report:
        report.status = status
        db.commit()
    return RedirectResponse("/admin/safety-reports", status_code=303)


@router.post("/api/safety/users/{target_id}/block")
async def block_user(
    target_id: int,
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    user = _current_user(request, db)
    if not user:
        return JSONResponse({"ok": False, "error": "Please log in again."}, status_code=401)
    if not _valid_csrf(request, csrf_token):
        return JSONResponse({"ok": False, "error": "This page expired. Refresh and try again."}, status_code=403)
    if target_id == user.id or not db.get(User, target_id):
        return JSONResponse({"ok": False, "error": "That account could not be found."}, status_code=404)
    existing = db.query(UserBlock).filter(UserBlock.blocker_id == user.id, UserBlock.blocked_id == target_id).first()
    if not existing:
        db.add(UserBlock(blocker_id=user.id, blocked_id=target_id))
    db.query(UserFollow).filter(
        ((UserFollow.follower_id == user.id) & (UserFollow.followed_id == target_id))
        | ((UserFollow.follower_id == target_id) & (UserFollow.followed_id == user.id))
    ).delete(synchronize_session=False)
    db.commit()
    return JSONResponse({"ok": True, "blocked": True})


@router.post("/api/safety/users/{target_id}/unblock")
async def unblock_user(
    target_id: int,
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    user = _current_user(request, db)
    if not user:
        return JSONResponse({"ok": False, "error": "Please log in again."}, status_code=401)
    if not _valid_csrf(request, csrf_token):
        return JSONResponse({"ok": False, "error": "This page expired. Refresh and try again."}, status_code=403)
    db.query(UserBlock).filter(UserBlock.blocker_id == user.id, UserBlock.blocked_id == target_id).delete(synchronize_session=False)
    db.commit()
    return JSONResponse({"ok": True, "blocked": False})


@router.post("/api/safety/report")
async def submit_safety_report(
    request: Request,
    reason: str = Form(...),
    details: str = Form(""),
    reported_user_id: int | None = Form(None),
    message_id: int | None = Form(None),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    user = _current_user(request, db)
    if not user:
        return JSONResponse({"ok": False, "error": "Please log in again."}, status_code=401)
    if not _valid_csrf(request, csrf_token):
        return JSONResponse({"ok": False, "error": "This page expired. Refresh and try again."}, status_code=403)
    details = details.strip()
    if reason not in REPORT_REASONS or len(details) > 1000:
        return JSONResponse({"ok": False, "error": "Choose a reason and keep details under 1000 characters."}, status_code=400)

    reported_message_id = None
    if message_id is not None:
        message = db.get(DirectMessage, message_id)
        if not message or user.id not in {message.sender_id, message.recipient_id}:
            return JSONResponse({"ok": False, "error": "That message could not be reported."}, status_code=404)
        if message.sender_id == user.id:
            return JSONResponse({"ok": False, "error": "You cannot report your own message."}, status_code=400)
        reported_user_id = message.sender_id
        reported_message_id = message.id
    target = db.get(User, reported_user_id) if reported_user_id else None
    if not target or target.id == user.id:
        return JSONResponse({"ok": False, "error": "Choose an account to report."}, status_code=400)

    cutoff = datetime.utcnow() - timedelta(hours=24)
    recent_count = db.query(SafetyReport.id).filter(
        SafetyReport.reporter_id == user.id,
        SafetyReport.created_at >= cutoff,
    ).count()
    if recent_count >= 10:
        return JSONResponse({"ok": False, "error": "You have reached the report limit for today."}, status_code=429)

    report = SafetyReport(
        reporter_id=user.id,
        reported_user_id=target.id,
        reported_username=target.username,
        reported_message_id=reported_message_id,
        reported_message_excerpt=message.content[:1500] if message_id is not None else "",
        reason=reason,
        details=details,
    )
    db.add(report)
    db.commit()
    return JSONResponse({"ok": True, "message": "Report sent. Thank you for helping keep Grapsy safe."})
