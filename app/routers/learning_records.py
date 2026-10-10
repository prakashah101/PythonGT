import json
import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.learning_record import LearningRecord
from app.models.user import User

router = APIRouter()
SCORE_RESULTS = {100: "CORRECT", 50: "PARTIAL", 0: "INCORRECT"}
CURRICULUM_PATH = Path(__file__).resolve().parents[2] / "data" / "curriculum.json"
with CURRICULUM_PATH.open(encoding="utf-8") as curriculum_file:
    COURSE_TOPICS = json.load(curriculum_file)["topics"]
TOPIC_IDS = {topic["id"] for topic in COURSE_TOPICS}
LEVEL_STARTS = {"Beginner": "variables", "Basic": "functions", "Intermediate": "dictionaries", "Advanced": "oop", "Professional": "testing_apis"}


@router.get("/api/topic-progress")
async def get_topic_progress(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    user = db.get(User, user_id) if user_id else None
    if not user:
        return JSONResponse({"ok": False, "error": "Please log in again."}, status_code=401)

    records = (
        db.query(LearningRecord)
        .filter(LearningRecord.user_id == user.id, LearningRecord.topic_id.in_(TOPIC_IDS))
        .order_by(LearningRecord.created_at.desc(), LearningRecord.id.desc())
        .all()
    )
    by_topic = {topic_id: [] for topic_id in TOPIC_IDS}
    for record in records:
        by_topic[record.topic_id].append(record)

    start_id = LEVEL_STARTS.get(user.learning_level or "", COURSE_TOPICS[0]["id"])
    start_index = next((index for index, topic in enumerate(COURSE_TOPICS) if topic["id"] == start_id), 0)
    mastered_ids = set()
    for topic_id, topic_records in by_topic.items():
        if len(topic_records) >= 2 and all(record.result == "CORRECT" for record in topic_records[:2]):
            mastered_ids.add(topic_id)

    next_topic_id = next(
        (topic["id"] for topic in COURSE_TOPICS[start_index:] if by_topic[topic["id"]] and topic["id"] not in mastered_ids),
        None,
    )
    if next_topic_id is None:
        next_topic_id = next(
            (topic["id"] for topic in COURSE_TOPICS[start_index:] if topic["id"] not in mastered_ids and not by_topic[topic["id"]]),
            None,
        )

    topic_data = []
    for index, topic in enumerate(COURSE_TOPICS):
        topic_records = by_topic[topic["id"]]
        if topic["id"] in mastered_ids:
            status = "mastered"
        elif topic_records:
            status = "in_progress"
        elif index < start_index:
            status = "foundation"
        elif topic["id"] == next_topic_id:
            status = "next"
        else:
            status = "upcoming"
        topic_data.append({
            "id": topic["id"],
            "status": status,
            "attempts": len(topic_records),
            "accuracy": round(sum(record.accuracy_score for record in topic_records) / len(topic_records)) if topic_records else None,
        })
    return JSONResponse({"ok": True, "topics": topic_data, "mastered": len(mastered_ids), "total": len(COURSE_TOPICS)})


@router.post("/api/learning-records")
async def save_learning_record(
    request: Request,
    question: str = Form(...),
    submitted_answer: str = Form(...),
    accuracy_score: int = Form(...),
    hint_used: str = Form("false"),
    topic_id: str = Form(""),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    user_id = request.session.get("user_id")
    if not user_id or not db.get(User, user_id):
        request.session.clear()
        return JSONResponse({"ok": False, "error": "Please log in again."}, status_code=401)

    expected_token = request.session.get("learning_record_csrf", "")
    if not expected_token or not secrets.compare_digest(csrf_token, expected_token):
        return JSONResponse({"ok": False, "error": "The page expired. Refresh and try again."}, status_code=403)

    question = question.strip()
    submitted_answer = submitted_answer.strip()
    if accuracy_score not in SCORE_RESULTS or hint_used not in {"true", "false"} or topic_id not in TOPIC_IDS | {""}:
        return JSONResponse({"ok": False, "error": "Invalid learning record data."}, status_code=400)
    if not question or len(question) > 10000 or not submitted_answer or len(submitted_answer) > 12000:
        return JSONResponse({"ok": False, "error": "The question or answer is too long or empty."}, status_code=400)

    record = LearningRecord(
        user_id=user_id,
        question=question,
        submitted_answer=submitted_answer,
        result=SCORE_RESULTS[accuracy_score],
        accuracy_score=accuracy_score,
        hint_used=hint_used == "true",
        learning_level=user.learning_level or "",
        topic_id=topic_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return JSONResponse({"ok": True, "id": record.id})
