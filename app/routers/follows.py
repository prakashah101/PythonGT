import secrets

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.user_block import UserBlock
from app.models.user_follow import UserFollow

router = APIRouter()


@router.get("/api/users/search")
async def search_users(request: Request, q: str = "", db: Session = Depends(get_db)):
    current_id = request.session.get("user_id")
    if not current_id:
        return JSONResponse({"ok": False, "error": "Please log in again."}, status_code=401)
    query = q.strip().lstrip("@").replace("%", "").replace("_", "")[:60]
    if len(query) < 2:
        return JSONResponse({"ok": True, "users": []})

    blocked_ids = {
        blocked_id for (blocked_id,) in db.query(UserBlock.blocked_id).filter(UserBlock.blocker_id == current_id).all()
    }
    blocked_ids.update(
        blocker_id for (blocker_id,) in db.query(UserBlock.blocker_id).filter(UserBlock.blocked_id == current_id).all()
    )
    pattern = f"%{query}%"
    users_query = db.query(User).filter(
        User.id != current_id,
        or_(
            User.username.ilike(pattern),
            User.first_name.ilike(pattern),
            User.last_name.ilike(pattern),
        ),
    )
    if blocked_ids:
        users_query = users_query.filter(~User.id.in_(blocked_ids))
    users = users_query.order_by(User.username.asc()).limit(15).all()
    user_ids = [user.id for user in users]
    following_ids = {
        followed_id
        for (followed_id,) in db.query(UserFollow.followed_id)
        .filter(UserFollow.follower_id == current_id, UserFollow.followed_id.in_(user_ids))
        .all()
    } if user_ids else set()
    follower_ids = {
        follower_id
        for (follower_id,) in db.query(UserFollow.follower_id)
        .filter(UserFollow.followed_id == current_id, UserFollow.follower_id.in_(user_ids))
        .all()
    } if user_ids else set()
    return JSONResponse({
        "ok": True,
        "users": [
            {
                "id": user.id,
                "username": user.username,
                "name": f"{user.first_name} {user.last_name}".strip(),
                "profile_picture_url": user.profile_picture_url,
                "following": user.id in following_ids,
                "follows_you": user.id in follower_ids,
                "can_message": user.id in following_ids and user.id in follower_ids,
            }
            for user in users
        ],
    })


@router.post("/users/{target_id}/follow")
async def follow_user(
    target_id: int,
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    follower_id = request.session.get("user_id")
    wants_json = "application/json" in request.headers.get("accept", "")
    if not follower_id:
        if wants_json:
            return JSONResponse({"ok": False, "error": "Please log in again."}, status_code=401)
        return RedirectResponse("/login", status_code=303)
    expected_token = request.session.get("project_csrf", "")
    if not expected_token or not secrets.compare_digest(expected_token, csrf_token):
        if wants_json:
            return JSONResponse({"ok": False, "error": "This page expired. Refresh and try again."}, status_code=403)
        return RedirectResponse("/projects?error=session#community", status_code=303)
    if target_id == follower_id or not db.get(User, target_id):
        if wants_json:
            return JSONResponse({"ok": False, "error": "That user could not be found."}, status_code=404)
        return RedirectResponse("/projects?error=follow#community", status_code=303)
    blocked = db.query(UserBlock.id).filter(
        ((UserBlock.blocker_id == follower_id) & (UserBlock.blocked_id == target_id))
        | ((UserBlock.blocker_id == target_id) & (UserBlock.blocked_id == follower_id))
    ).first()
    if blocked:
        if wants_json:
            return JSONResponse({"ok": False, "error": "This follow is unavailable."}, status_code=403)
        return RedirectResponse("/projects?error=follow#community", status_code=303)
    relationship = (
        db.query(UserFollow)
        .filter(UserFollow.follower_id == follower_id, UserFollow.followed_id == target_id)
        .first()
    )
    if not relationship:
        db.add(UserFollow(follower_id=follower_id, followed_id=target_id))
        db.commit()
    if wants_json:
        return JSONResponse({"ok": True, "following": True})
    return RedirectResponse("/projects#community", status_code=303)


@router.post("/users/{target_id}/unfollow")
async def unfollow_user(
    target_id: int,
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    follower_id = request.session.get("user_id")
    wants_json = "application/json" in request.headers.get("accept", "")
    if not follower_id:
        if wants_json:
            return JSONResponse({"ok": False, "error": "Please log in again."}, status_code=401)
        return RedirectResponse("/login", status_code=303)
    expected_token = request.session.get("project_csrf", "")
    if not expected_token or not secrets.compare_digest(expected_token, csrf_token):
        if wants_json:
            return JSONResponse({"ok": False, "error": "This page expired. Refresh and try again."}, status_code=403)
        return RedirectResponse("/projects?error=session#community", status_code=303)
    db.query(UserFollow).filter(
        UserFollow.follower_id == follower_id,
        UserFollow.followed_id == target_id,
    ).delete(synchronize_session=False)
    db.commit()
    if wants_json:
        return JSONResponse({"ok": True, "following": False})
    return RedirectResponse("/projects#community", status_code=303)
