import secrets

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.project import Project
from app.models.user import User
from app.models.user_block import UserBlock
from app.models.user_follow import UserFollow
from app.project_starters import PROJECT_STARTERS
from app.timezone import to_nepal_time

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[2] / "templates"))
MAX_CODE_LENGTH = 60_000


def logged_in_user(request: Request, db: Session):
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = db.get(User, user_id)
    if not user:
        request.session.clear()
    return user


def valid_csrf(request: Request, token: str) -> bool:
    expected = request.session.get("project_csrf", "")
    return bool(expected and secrets.compare_digest(expected, token))


@router.get("/projects")
async def projects_page(request: Request, db: Session = Depends(get_db)):
    user = logged_in_user(request, db)
    csrf_token = ""
    projects = []
    if user:
        csrf_token = request.session.get("project_csrf")
        if not csrf_token:
            csrf_token = secrets.token_urlsafe(32)
            request.session["project_csrf"] = csrf_token
        projects = (
            db.query(Project)
            .filter(Project.user_id == user.id)
            .order_by(Project.updated_at.desc(), Project.id.desc())
            .all()
        )
    community_query = (
        db.query(Project, User)
        .join(User, User.id == Project.user_id)
        .filter(Project.is_public.is_(True))
    )
    if user:
        community_query = community_query.filter(Project.user_id != user.id)
        blocked_ids = {
            blocked_id for (blocked_id,) in db.query(UserBlock.blocked_id).filter(UserBlock.blocker_id == user.id).all()
        }
        blocked_ids.update(
            blocker_id for (blocker_id,) in db.query(UserBlock.blocker_id).filter(UserBlock.blocked_id == user.id).all()
        )
        if blocked_ids:
            community_query = community_query.filter(~Project.user_id.in_(blocked_ids))
    community_projects = (
        community_query.order_by(Project.updated_at.desc(), Project.id.desc()).all()
    )
    followed_user_ids = set()
    friend_user_ids = set()
    if user:
        followed_user_ids = {
            followed_id
            for (followed_id,) in db.query(UserFollow.followed_id)
            .filter(UserFollow.follower_id == user.id)
            .all()
        }
        follower_user_ids = {
            follower_id
            for (follower_id,) in db.query(UserFollow.follower_id)
            .filter(UserFollow.followed_id == user.id)
            .all()
        }
        friend_user_ids = followed_user_ids & follower_user_ids
    follower_counts = dict(
        db.query(UserFollow.followed_id, func.count(UserFollow.id))
        .group_by(UserFollow.followed_id)
        .all()
    )
    return templates.TemplateResponse(
        request=request,
        name="projects.html",
        context={
            "username": user.username if user else None,
            "projects": projects,
            "community_projects": community_projects,
            "current_user_id": user.id if user else None,
            "followed_user_ids": followed_user_ids,
            "friend_user_ids": friend_user_ids,
            "follower_counts": follower_counts,
            "starters": PROJECT_STARTERS,
            "csrf_token": csrf_token,
            "safety_csrf": request.session.setdefault("safety_csrf", secrets.token_urlsafe(32)),
            "to_nepal_time": to_nepal_time,
        },
    )


@router.post("/projects/create")
async def create_project(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    code: str = Form(""),
    visibility: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    user = logged_in_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if not valid_csrf(request, csrf_token):
        return RedirectResponse("/projects?error=session", status_code=303)
    title = title.strip()
    if visibility not in {"public", "private"} or not title or len(title) > 100 or len(description) > 500 or len(code) > MAX_CODE_LENGTH:
        return RedirectResponse("/projects?error=invalid", status_code=303)
    project = Project(user_id=user.id, title=title, description=description.strip(), code=code, is_public=visibility == "public")
    db.add(project)
    db.commit()
    return RedirectResponse(f"/projects#{project.id}", status_code=303)


@router.post("/projects/starter/{slug}/create")
async def create_from_starter(
    slug: str,
    request: Request,
    csrf_token: str = Form(...),
    visibility: str = Form(...),
    db: Session = Depends(get_db),
):
    user = logged_in_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if not valid_csrf(request, csrf_token):
        return RedirectResponse("/projects?error=session", status_code=303)
    if visibility not in {"public", "private"}:
        return RedirectResponse("/projects?error=invalid#library", status_code=303)
    starter = next((item for item in PROJECT_STARTERS if item["slug"] == slug), None)
    if not starter:
        return RedirectResponse("/projects?error=missing#library", status_code=303)
    project = Project(
        user_id=user.id,
        title=starter["title"],
        description=starter["description"],
        code=starter["code"],
        is_public=visibility == "public",
    )
    db.add(project)
    db.commit()
    return RedirectResponse(f"/projects#{project.id}", status_code=303)


@router.post("/projects/{project_id}/save")
async def save_project(
    project_id: int,
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    code: str = Form(""),
    visibility: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    user = logged_in_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if not valid_csrf(request, csrf_token):
        return RedirectResponse("/projects?error=session", status_code=303)
    project = db.query(Project).filter(Project.id == project_id, Project.user_id == user.id).first()
    if not project:
        return RedirectResponse("/projects?error=missing", status_code=303)
    title = title.strip()
    if visibility not in {"public", "private"} or not title or len(title) > 100 or len(description) > 500 or len(code) > MAX_CODE_LENGTH:
        return RedirectResponse(f"/projects?error=invalid#{project.id}", status_code=303)
    project.title = title
    project.description = description.strip()
    project.code = code
    project.is_public = visibility == "public"
    db.commit()
    return RedirectResponse(f"/projects?saved=1#{project.id}", status_code=303)


@router.post("/projects/{project_id}/delete")
async def delete_project(
    project_id: int,
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    user = logged_in_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if not valid_csrf(request, csrf_token):
        return RedirectResponse("/projects?error=session", status_code=303)
    project = db.query(Project).filter(Project.id == project_id, Project.user_id == user.id).first()
    if project:
        db.delete(project)
        db.commit()
    return RedirectResponse("/projects?deleted=1", status_code=303)
