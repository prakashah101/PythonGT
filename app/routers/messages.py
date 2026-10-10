import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.direct_message import DirectMessage
from app.models.user import User
from app.models.user_block import UserBlock
from app.models.user_follow import UserFollow
from app.timezone import to_nepal_time

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[2] / "templates"))
MAX_MESSAGE_LENGTH = 4000


def _current_user(request: Request, db: Session):
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = db.get(User, user_id)
    if not user:
        request.session.clear()
    return user


def _are_mutual_follows(db: Session, first_id: int, second_id: int) -> bool:
    if first_id == second_id:
        return False
    blocked = db.query(UserBlock.id).filter(
        ((UserBlock.blocker_id == first_id) & (UserBlock.blocked_id == second_id))
        | ((UserBlock.blocker_id == second_id) & (UserBlock.blocked_id == first_id))
    ).first()
    if blocked:
        return False
    first_follows_second = db.query(UserFollow.id).filter(
        UserFollow.follower_id == first_id,
        UserFollow.followed_id == second_id,
    ).first()
    second_follows_first = db.query(UserFollow.id).filter(
        UserFollow.follower_id == second_id,
        UserFollow.followed_id == first_id,
    ).first()
    return bool(first_follows_second and second_follows_first)


def _serialize_message(message: DirectMessage, current_user_id: int) -> dict:
    return {
        "id": message.id,
        "sender_id": message.sender_id,
        "content": message.content,
        "created_at": to_nepal_time(message.created_at).strftime("%b %d, %Y · %H:%M NPT"),
        "mine": message.sender_id == current_user_id,
    }


def _contact_data(db: Session, user: User) -> list[dict]:
    following_ids = {
        followed_id for (followed_id,) in db.query(UserFollow.followed_id)
        .filter(UserFollow.follower_id == user.id).all()
    }
    follower_ids = {
        follower_id for (follower_id,) in db.query(UserFollow.follower_id)
        .filter(UserFollow.followed_id == user.id).all()
    }
    blocked_ids = {
        blocked_id for (blocked_id,) in db.query(UserBlock.blocked_id).filter(UserBlock.blocker_id == user.id).all()
    }
    blocked_ids.update(
        blocker_id for (blocker_id,) in db.query(UserBlock.blocker_id).filter(UserBlock.blocked_id == user.id).all()
    )
    following_ids.difference_update(blocked_ids)
    if not following_ids:
        return []
    friends = db.query(User).filter(User.id.in_(following_ids)).order_by(User.username.asc()).all()
    contacts = []
    for friend in friends:
        can_message = friend.id in follower_ids
        last_message = (
            db.query(DirectMessage)
            .filter(or_(
                and_(DirectMessage.sender_id == user.id, DirectMessage.recipient_id == friend.id),
                and_(DirectMessage.sender_id == friend.id, DirectMessage.recipient_id == user.id),
            ))
            .order_by(DirectMessage.id.desc())
            .first()
        ) if can_message else None
        unread_count = (
            db.query(DirectMessage)
            .filter(
                DirectMessage.sender_id == friend.id,
                DirectMessage.recipient_id == user.id,
                DirectMessage.read_at.is_(None),
            )
            .count()
        ) if can_message else 0
        contacts.append({"user": friend, "last_message": last_message, "unread_count": unread_count, "can_message": can_message})
    contacts.sort(key=lambda contact: (
        contact["can_message"],
        contact["last_message"].id if contact["last_message"] else 0,
        contact["user"].username.lower(),
    ), reverse=True)
    return contacts


@router.get("/messages")
async def messages_page(request: Request, db: Session = Depends(get_db)):
    user = _current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    csrf_token = request.session.get("messages_csrf")
    if not csrf_token:
        csrf_token = secrets.token_urlsafe(32)
        request.session["messages_csrf"] = csrf_token
    return templates.TemplateResponse(
        request=request,
        name="messages.html",
        context={
            "user": user,
            "contacts": _contact_data(db, user),
            "selected_friend": None,
            "messages": [],
            "csrf_token": csrf_token,
            "safety_csrf": request.session.setdefault("safety_csrf", secrets.token_urlsafe(32)),
            "to_nepal_time": to_nepal_time,
        },
    )


@router.get("/messages/{friend_id}")
async def conversation_page(friend_id: int, request: Request, db: Session = Depends(get_db)):
    user = _current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    friend = db.get(User, friend_id)
    if not friend or not _are_mutual_follows(db, user.id, friend.id):
        return RedirectResponse("/messages?error=not_friends", status_code=303)
    csrf_token = request.session.get("messages_csrf")
    if not csrf_token:
        csrf_token = secrets.token_urlsafe(32)
        request.session["messages_csrf"] = csrf_token
    rows = (
        db.query(DirectMessage)
        .filter(or_(
            and_(DirectMessage.sender_id == user.id, DirectMessage.recipient_id == friend.id),
            and_(DirectMessage.sender_id == friend.id, DirectMessage.recipient_id == user.id),
        ))
        .order_by(DirectMessage.id.desc())
        .limit(200)
        .all()
    )
    messages = [_serialize_message(message, user.id) for message in reversed(rows)]
    db.query(DirectMessage).filter(
        DirectMessage.sender_id == friend.id,
        DirectMessage.recipient_id == user.id,
        DirectMessage.read_at.is_(None),
    ).update({DirectMessage.read_at: datetime.utcnow()}, synchronize_session=False)
    db.commit()
    return templates.TemplateResponse(
        request=request,
        name="messages.html",
        context={
            "user": user,
            "contacts": _contact_data(db, user),
            "selected_friend": friend,
            "messages": messages,
            "csrf_token": csrf_token,
            "safety_csrf": request.session.setdefault("safety_csrf", secrets.token_urlsafe(32)),
            "to_nepal_time": to_nepal_time,
        },
    )


@router.get("/api/messages/{friend_id}")
async def poll_messages(
    friend_id: int,
    request: Request,
    after_id: int = 0,
    db: Session = Depends(get_db),
):
    user = _current_user(request, db)
    if not user:
        return JSONResponse({"ok": False, "error": "Please log in again."}, status_code=401)
    if not _are_mutual_follows(db, user.id, friend_id):
        return JSONResponse({"ok": False, "error": "You can chat after you follow each other."}, status_code=403)
    rows = (
        db.query(DirectMessage)
        .filter(
            or_(
                and_(DirectMessage.sender_id == user.id, DirectMessage.recipient_id == friend_id),
                and_(DirectMessage.sender_id == friend_id, DirectMessage.recipient_id == user.id),
            ),
            DirectMessage.id > max(0, after_id),
        )
        .order_by(DirectMessage.id.asc())
        .limit(100)
        .all()
    )
    unread_ids = [message.id for message in rows if message.sender_id == friend_id and message.read_at is None]
    if unread_ids:
        db.query(DirectMessage).filter(DirectMessage.id.in_(unread_ids)).update(
            {DirectMessage.read_at: datetime.utcnow()}, synchronize_session=False
        )
        db.commit()
    return JSONResponse({"ok": True, "messages": [_serialize_message(message, user.id) for message in rows]})


@router.post("/api/messages/{friend_id}")
async def send_message(
    friend_id: int,
    request: Request,
    content: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    user = _current_user(request, db)
    if not user:
        return JSONResponse({"ok": False, "error": "Please log in again."}, status_code=401)
    expected_token = request.session.get("messages_csrf", "")
    if not expected_token or not secrets.compare_digest(expected_token, csrf_token):
        return JSONResponse({"ok": False, "error": "This chat expired. Refresh the page and try again."}, status_code=403)
    friend = db.get(User, friend_id)
    if not friend or not _are_mutual_follows(db, user.id, friend_id):
        return JSONResponse({"ok": False, "error": "You can chat after you follow each other."}, status_code=403)
    content = content.strip()
    if not content or len(content) > MAX_MESSAGE_LENGTH:
        return JSONResponse({"ok": False, "error": "Messages must contain 1–4000 characters."}, status_code=400)
    message = DirectMessage(sender_id=user.id, recipient_id=friend_id, content=content)
    db.add(message)
    db.commit()
    db.refresh(message)
    return JSONResponse({"ok": True, "message": _serialize_message(message, user.id)})
