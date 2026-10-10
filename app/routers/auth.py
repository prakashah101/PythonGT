import hashlib
import hmac
import logging
import secrets
import smtplib
import email.message
import re
import time
import uuid
from datetime import datetime
from pathlib import Path

import bcrypt
from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import (
    BASE_URL, FACEBOOK_CLIENT_ID, FACEBOOK_CLIENT_SECRET, FACEBOOK_GRAPH_VERSION,
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, SMTP_FROM, SMTP_HOST,
    SMTP_PASSWORD, SMTP_PORT, SMTP_USER, SECRET_KEY, TERMS_VERSION,
)
from app.database import get_db
from app.models.feedback import Feedback
from app.models.learning_record import LearningRecord
from app.models.project import Project
from app.models.user_follow import UserFollow
from app.models.direct_message import DirectMessage
from app.models.safety_report import SafetyReport
from app.models.user_block import UserBlock
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)
oauth = OAuth()

if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
    oauth.register(
        name="google", client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
if FACEBOOK_CLIENT_ID and FACEBOOK_CLIENT_SECRET:
    oauth.register(
        name="facebook", client_id=FACEBOOK_CLIENT_ID,
        client_secret=FACEBOOK_CLIENT_SECRET,
        access_token_url=f"https://graph.facebook.com/{FACEBOOK_GRAPH_VERSION}/oauth/access_token",
        authorize_url=f"https://www.facebook.com/{FACEBOOK_GRAPH_VERSION}/dialog/oauth",
        api_base_url=f"https://graph.facebook.com/{FACEBOOK_GRAPH_VERSION}/",
        token_endpoint_auth_method="client_secret_post",
        client_kwargs={"scope": "email,public_profile"},
    )


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def _otp_digest(email: str, otp: str) -> str:
    return hmac.new(SECRET_KEY.encode(), f"{email}:{otp}".encode(), hashlib.sha256).hexdigest()


def _login(request: Request, user: User) -> None:
    request.session.clear()
    request.session["user_id"] = user.id
    request.session["username"] = user.username
    request.session["profile_picture_url"] = user.profile_picture_url


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@router.post("/api/legal/accept")
async def accept_legal_terms(
    request: Request,
    accepted: str = Form(...),
    csrf_token: str = Form(...),
):
    expected = request.session.get("terms_csrf", "")
    if not expected or not secrets.compare_digest(expected, csrf_token):
        return JSONResponse({"ok": False, "error": "This page expired. Refresh and try again."}, status_code=403)
    if accepted != "yes":
        return JSONResponse({"ok": False, "error": "Please accept the Terms and Privacy Policy to continue."}, status_code=400)
    request.session["accepted_terms_version"] = TERMS_VERSION
    request.session["accepted_terms_at"] = datetime.utcnow().isoformat()
    return JSONResponse({"ok": True})


@router.post("/api/account/delete")
async def delete_account(
    request: Request,
    confirmation: str = Form(...),
    current_password: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    user_id = request.session.get("user_id")
    user = db.get(User, user_id) if user_id else None
    if not user:
        request.session.clear()
        return JSONResponse({"ok": False, "error": "Please log in again."}, status_code=401)

    expected_token = request.session.get("account_action_csrf", "")
    if not expected_token or not secrets.compare_digest(csrf_token, expected_token):
        return JSONResponse({"ok": False, "error": "This form expired. Refresh the profile page and try again."}, status_code=403)
    if confirmation.strip() != user.username:
        return JSONResponse({"ok": False, "error": "Enter your exact username to confirm account deletion."}, status_code=400)
    if user.auth_provider != "password":
        return JSONResponse({"ok": False, "error": "Set a password in your profile before deleting this account."}, status_code=400)
    if len(current_password.encode()) > 72 or not bcrypt.checkpw(current_password.encode(), user.hashed_password.encode()):
        return JSONResponse({"ok": False, "error": "The password is incorrect."}, status_code=400)

    avatar_path = None
    if user.profile_picture_url:
        avatar_dir = Path(__file__).resolve().parents[2] / "static" / "uploads" / "avatars"
        avatar_name = Path(user.profile_picture_url).name
        if avatar_name.startswith(f"{user.id}_"):
            avatar_path = avatar_dir / avatar_name

    db.query(Feedback).filter(Feedback.user_id == user.id).delete(synchronize_session=False)
    db.query(LearningRecord).filter(LearningRecord.user_id == user.id).delete(synchronize_session=False)
    db.query(Project).filter(Project.user_id == user.id).delete(synchronize_session=False)
    db.query(UserFollow).filter(
        (UserFollow.follower_id == user.id) | (UserFollow.followed_id == user.id)
    ).delete(synchronize_session=False)
    db.query(DirectMessage).filter(
        (DirectMessage.sender_id == user.id) | (DirectMessage.recipient_id == user.id)
    ).delete(synchronize_session=False)
    db.query(UserBlock).filter(
        (UserBlock.blocker_id == user.id) | (UserBlock.blocked_id == user.id)
    ).delete(synchronize_session=False)
    db.query(SafetyReport).filter(SafetyReport.reporter_id == user.id).update(
        {SafetyReport.reporter_id: None}, synchronize_session=False
    )
    db.query(SafetyReport).filter(SafetyReport.reported_user_id == user.id).update(
        {SafetyReport.reported_user_id: None}, synchronize_session=False
    )
    db.delete(user)
    db.commit()
    request.session.clear()
    if avatar_path:
        try:
            avatar_path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not remove a deleted user's profile picture from disk")
    return JSONResponse({"ok": True, "redirect": "/"})


@router.post("/api/profile-picture")
async def upload_profile_picture(
    request: Request,
    picture: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse({"ok": False, "error": "Please log in again."}, status_code=401)

    contents = await picture.read(2 * 1024 * 1024 + 1)
    if len(contents) > 2 * 1024 * 1024:
        return JSONResponse({"ok": False, "error": "Choose an image smaller than 2 MB."}, status_code=413)

    signatures = (
        (".png", "image/png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
        (".jpg", "image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
        (".gif", "image/gif", lambda data: data.startswith((b"GIF87a", b"GIF89a"))),
        (".webp", "image/webp", lambda data: len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"),
    )
    image_format = next((entry for entry in signatures if entry[2](contents)), None)
    if not image_format or picture.content_type != image_format[1]:
        return JSONResponse({"ok": False, "error": "Upload a PNG, JPG, GIF, or WebP image."}, status_code=400)

    user = db.get(User, user_id)
    if not user:
        request.session.clear()
        return JSONResponse({"ok": False, "error": "Account not found. Please log in again."}, status_code=401)

    upload_dir = Path(__file__).resolve().parents[2] / "static" / "uploads" / "avatars"
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{user.id}_{uuid.uuid4().hex}{image_format[0]}"
    destination = upload_dir / filename
    destination.write_bytes(contents)
    user.profile_picture_url = f"/static/uploads/avatars/{filename}"
    try:
        db.commit()
    except Exception:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise
    request.session["profile_picture_url"] = user.profile_picture_url
    return JSONResponse({"ok": True, "profile_picture_url": user.profile_picture_url})


def _send_otp_email(to: str, otp: str) -> None:
    if not SMTP_HOST or not SMTP_USER:
        print(f"\n{'='*40}\n  OTP for {to}: {otp}\n{'='*40}\n")
        return
    msg = email.message.EmailMessage()
    msg["Subject"] = "Your Grapsy verification code"
    msg["From"] = SMTP_FROM
    msg["To"] = to
    msg.set_content(f"Your Grapsy verification code is: {otp}\n\nIt expires in 10 minutes.")
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.send_message(msg)


@router.post("/api/send-otp")
async def send_otp(request: Request, email: str = Form(...), db: Session = Depends(get_db)):
    email = email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        return JSONResponse({"ok": False, "error": "Enter a valid email address."}, status_code=400)
    if db.query(User).filter(User.email == email).first():
        return JSONResponse({"ok": False, "error": "Email already registered."}, status_code=409)
    now = time.time()
    if now - request.session.get("otp_sent_at", 0) < 60:
        return JSONResponse({"ok": False, "error": "Please wait before requesting another code."}, status_code=429)
    otp = f"{secrets.randbelow(1_000_000):06d}"
    request.session["otp_digest"] = _otp_digest(email, otp)
    request.session["otp_email"] = email
    request.session["otp_expires_at"] = now + 600
    request.session["otp_sent_at"] = now
    request.session.pop("email_verified", None)
    _send_otp_email(email, otp)
    return JSONResponse({"ok": True, "cooldown": 60})


@router.post("/api/verify-otp")
async def verify_otp(request: Request, otp: str = Form(...)):
    email = request.session.get("otp_email", "")
    expected = request.session.get("otp_digest")
    expires = request.session.get("otp_expires_at", 0)
    supplied = _otp_digest(email, otp)
    if not expected or time.time() > expires or not secrets.compare_digest(supplied, expected):
        return JSONResponse({"ok": False, "error": "Incorrect or expired code."}, status_code=400)
    request.session["email_verified"] = request.session.get("otp_email")
    return JSONResponse({"ok": True})


@router.get("/api/check-username")
async def check_username(username: str, db: Session = Depends(get_db)):
    taken = db.query(User).filter(User.username == username.strip()).first() is not None
    return JSONResponse({"available": not taken})


@router.get("/api/check-unique")
async def check_unique(field: str, value: str, db: Session = Depends(get_db)):
    if field != "phone":
        return JSONResponse({"available": False}, status_code=400)
    taken = db.query(User).filter(User.phone == value.strip()).first() is not None
    return JSONResponse({"available": not taken})


@router.post("/signup")
async def signup(
    request: Request,
    first_name: str = Form(...), last_name: str = Form(...),
    username: str = Form(...), email: str = Form(...), phone: str = Form(...),
    password: str = Form(...), confirm_password: str = Form(...),
    date_of_birth: str = Form(""), relationship_status: str = Form(""),
    location: str = Form(""), terms: str = Form(""),
    db: Session = Depends(get_db),
):
    email, username, phone = email.strip().lower(), username.strip(), phone.strip()
    errors = []
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        errors.append("Enter a valid email address.")
    if not first_name.strip() or not last_name.strip():
        errors.append("Enter your first and last name.")
    if len(re.sub(r"\D", "", phone)) < 7:
        errors.append("Enter a valid phone number.")
    if not request.session.get("email_verified") or request.session.get("email_verified") != email:
        errors.append("Please verify this email address before creating your account.")
    if password != confirm_password:
        errors.append("Passwords do not match.")
    if len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    if len(password.encode()) > 72:
        errors.append("Password must be 72 bytes or fewer.")
    if not terms or request.session.get("accepted_terms_version") != TERMS_VERSION:
        errors.append("Please accept the current Terms and Privacy Policy before creating your account.")
    if not re.fullmatch(r"[A-Za-z0-9_]{3,30}", username):
        errors.append("Username must be 3–30 characters and use only letters, numbers, or underscores.")
    if db.query(User).filter(User.email == email).first():
        errors.append("Email already registered.")
    if db.query(User).filter(User.username == username).first():
        errors.append("Username already taken.")
    if db.query(User).filter(User.phone == phone).first():
        errors.append("Phone number already registered.")
    if errors:
        return JSONResponse({"ok": False, "errors": errors}, status_code=400)

    user = User(
        first_name=first_name.strip(), last_name=last_name.strip(), username=username,
        email=email, phone=phone, hashed_password=_hash_password(password),
        date_of_birth=date_of_birth or None, relationship_status=relationship_status or None,
        location=location or None, is_email_verified=True, created_at=datetime.utcnow(),
        terms_version=TERMS_VERSION, terms_accepted_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    _login(request, user)
    return JSONResponse({"ok": True, "redirect": "/dashboard"})


@router.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if not user or not bcrypt.checkpw(password.encode(), user.hashed_password.encode()):
        return JSONResponse({"ok": False, "error": "Email or password is incorrect."}, status_code=401)
    _login(request, user)
    return JSONResponse({"ok": True, "redirect": "/dashboard"})


@router.get("/auth/{provider}")
async def oauth_login(provider: str, request: Request):
    flow = "signup" if request.query_params.get("flow") == "signup" else "login"
    if flow == "signup" and request.session.get("accepted_terms_version") != TERMS_VERSION:
        return RedirectResponse("/signup?error=terms_required", status_code=303)
    request.session["oauth_flow"] = flow
    client = getattr(oauth, provider, None) if provider in {"google", "facebook"} else None
    if client is None:
        return RedirectResponse(f"/{flow}?error=provider_unconfigured", status_code=303)
    redirect_uri = f"{BASE_URL}/auth/{provider}/callback"
    return await client.authorize_redirect(request, redirect_uri)


@router.get("/auth/{provider}/callback", name="oauth_callback")
async def oauth_callback(provider: str, request: Request, db: Session = Depends(get_db)):
    flow = request.session.pop("oauth_flow", "login")
    error_page = "/signup" if flow == "signup" else "/login"
    if flow == "signup" and request.session.get("accepted_terms_version") != TERMS_VERSION:
        return RedirectResponse("/signup?error=terms_required", status_code=303)
    client = getattr(oauth, provider, None) if provider in {"google", "facebook"} else None
    if client is None:
        return RedirectResponse(f"{error_page}?error=provider_unconfigured", status_code=303)
    try:
        token = await client.authorize_access_token(request)
        if provider == "google":
            # Current Authlib validates an OIDC ID token inside
            # authorize_access_token and attaches the claims as ``userinfo``.
            # Older code called parse_id_token(request, token), which no longer
            # matches Authlib's method signature and raises KeyError on Request.
            profile = token.get("userinfo")
            if profile is None:
                profile = await client.userinfo(token=token)
            email, name = profile.get("email"), profile.get("name", "")
            verified = bool(profile.get("email_verified"))
        else:
            response = await client.get("me?fields=id,name,email", token=token)
            profile = response.json()
            email, name = profile.get("email"), profile.get("name", "")
            verified = bool(email)
        if not email or not verified:
            return RedirectResponse(f"{error_page}?error=email_unverified", status_code=303)
        email = email.strip().lower()
        user = db.query(User).filter(User.email == email).first()
        is_new_user = user is None
        if is_new_user and request.session.get("accepted_terms_version") != TERMS_VERSION:
            return RedirectResponse("/signup?error=terms_required", status_code=303)
        if is_new_user:
            first, _, last = name.partition(" ")
            stem = re.sub(r"[^a-zA-Z0-9_]", "", email.split("@", 1)[0]).lower()[:22] or "learner"
            username, suffix = stem, 1
            while db.query(User).filter(User.username == username).first():
                tail = str(suffix)
                username, suffix = f"{stem[:30-len(tail)]}{tail}", suffix + 1
            user = User(
                first_name=first[:100] or "Learner", last_name=last[:100], username=username,
                email=email, phone="", hashed_password=_hash_password(secrets.token_urlsafe(32)),
                auth_provider=provider,
                is_email_verified=True, created_at=datetime.utcnow(),
            )
            db.add(user)
        if flow == "signup" or is_new_user:
            user.terms_version = TERMS_VERSION
            user.terms_accepted_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        _login(request, user)
        return RedirectResponse("/dashboard", status_code=303)
    except (OAuthError, ValueError, KeyError):
        logger.exception("OAuth callback failed for provider %s", provider)
        return RedirectResponse(f"{error_page}?error=oauth_failed", status_code=303)
