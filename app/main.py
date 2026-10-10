import os
import json
import secrets
from datetime import timezone
from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import func, inspect, text
from sqlalchemy.orm import Session

from app.config import SECRET_KEY
from app.database import Base, engine, get_db
from app.timezone import NEPAL_TIMEZONE
from app.models.user import User
from app.models.feedback import Feedback  # Register feedback table before create_all.
from app.models.learning_record import LearningRecord  # Register learning history table.
from app.models.project import Project  # Register saved projects table.
from app.models.user_follow import UserFollow  # Register social follow relations.
from app.models.direct_message import DirectMessage  # Register private chat messages.
from app.models.user_block import UserBlock  # Register account blocks.
from app.models.safety_report import SafetyReport  # Register user safety reports.
from app.routers import auth, feedback, learning_records, profile, projects, follows, messages, safety

# Resolve paths relative to the project root (one level up from app/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Create DB tables on startup
Base.metadata.create_all(bind=engine)
user_columns = {column["name"] for column in inspect(engine).get_columns("users")}
user_column_migrations = {
    "profile_picture_url": "VARCHAR(255)",
    "auth_provider": "VARCHAR(16) NOT NULL DEFAULT 'password'",
    "learning_level": "VARCHAR(30)",
    "code_submission_count": "INTEGER NOT NULL DEFAULT 0",
    "last_review_result": "VARCHAR(20)",
    "terms_version": "VARCHAR(30)",
    "terms_accepted_at": "DATETIME",
}
with engine.begin() as connection:
    for column_name, column_type in user_column_migrations.items():
        if column_name not in user_columns:
            connection.execute(text(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}"))
    if "auth_provider" not in user_columns:
        connection.execute(text("UPDATE users SET auth_provider = 'oauth' WHERE phone IS NULL OR TRIM(phone) = ''"))
    learning_record_columns = {column["name"] for column in inspect(connection).get_columns("learning_records")}
    if "topic_id" not in learning_record_columns:
        connection.execute(text("ALTER TABLE learning_records ADD COLUMN topic_id VARCHAR(50) NOT NULL DEFAULT ''"))
    project_columns = {column["name"] for column in inspect(connection).get_columns("projects")}
    if "is_public" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN is_public BOOLEAN NOT NULL DEFAULT FALSE"))
    safety_report_columns = {column["name"] for column in inspect(connection).get_columns("safety_reports")}
    if "reported_message_excerpt" not in safety_report_columns:
        connection.execute(text("ALTER TABLE safety_reports ADD COLUMN reported_message_excerpt TEXT NOT NULL DEFAULT ''"))

app = FastAPI()

# Session middleware (required for OTP & login state)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Serve everything in static/ at /static
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# Jinja2 templates from the root templates/ folder
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
with open(os.path.join(BASE_DIR, "data", "curriculum.json"), encoding="utf-8") as curriculum_file:
    COURSE_PATH = json.load(curriculum_file)

# Include routers
app.include_router(auth.router)
app.include_router(feedback.router)
app.include_router(learning_records.router)
app.include_router(profile.router)
app.include_router(projects.router)
app.include_router(follows.router)
app.include_router(messages.router)
app.include_router(safety.router)


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="landing.html")


@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    terms_csrf = request.session.get("terms_csrf")
    if not terms_csrf:
        terms_csrf = secrets.token_urlsafe(32)
        request.session["terms_csrf"] = terms_csrf
    return templates.TemplateResponse(
        request=request,
        name="signup.html",
        context={"terms_csrf": terms_csrf},
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")


@app.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    return templates.TemplateResponse(request=request, name="privacy.html")


@app.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request):
    return templates.TemplateResponse(request=request, name="terms.html")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "username": request.session.get("username", "learner"),
            "profile_picture_url": request.session.get("profile_picture_url"),
            "course_path": COURSE_PATH,
            "learning_record_csrf": request.session.setdefault("learning_record_csrf", secrets.token_urlsafe(32)),
            "project_csrf": request.session.setdefault("project_csrf", secrets.token_urlsafe(32)),
            "safety_csrf": request.session.setdefault("safety_csrf", secrets.token_urlsafe(32)),
        },
    )


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=303)
    user = db.get(User, user_id)
    if not user:
        request.session.clear()
        return RedirectResponse("/login", status_code=303)
    account_action_csrf = request.session.get("account_action_csrf")
    if not account_action_csrf:
        account_action_csrf = secrets.token_urlsafe(32)
        request.session["account_action_csrf"] = account_action_csrf
    learning_records = (
        db.query(LearningRecord)
        .filter(LearningRecord.user_id == user.id)
        .order_by(LearningRecord.created_at.desc(), LearningRecord.id.desc())
        .all()
    )
    followers_count = db.query(func.count(UserFollow.id)).filter(UserFollow.followed_id == user.id).scalar() or 0
    following_count = db.query(func.count(UserFollow.id)).filter(UserFollow.follower_id == user.id).scalar() or 0
    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={
            "user": user,
            "course_path": COURSE_PATH,
            "learning_records": learning_records,
            "followers_count": followers_count,
            "following_count": following_count,
            "account_action_csrf": account_action_csrf,
            "timezone": timezone,
            "nepal_timezone": NEPAL_TIMEZONE,
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
