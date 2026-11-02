from typing import Literal

from fastapi import APIRouter

from api.context import Actor, Db, DecimalRoute, Key, orchestration_service
from schemas.banking import BirthdayTaskRequest, PersonalEventRequest


router = APIRouter(prefix="/api", tags=["tasks"], route_class=DecimalRoute)


@router.get("/personal-events")
def list_personal_events(user: Actor, db: Db):
    return orchestration_service(db).list_events(user)


@router.post("/personal-events", status_code=201)
def create_personal_event(body: PersonalEventRequest, user: Actor, db: Db, key: Key):
    return orchestration_service(db).save_event(user, body, key)


@router.get("/tasks")
def list_tasks(user: Actor, db: Db):
    return orchestration_service(db).list(user)


@router.post("/tasks/birthday", status_code=201)
def create_birthday_task(body: BirthdayTaskRequest, user: Actor, db: Db, key: Key):
    return orchestration_service(db).create_birthday_task(user, body, key)


@router.get("/tasks/{task_id}")
def get_task(task_id: str, user: Actor, db: Db):
    return orchestration_service(db).view(user, task_id)


@router.post("/tasks/{task_id}/{command}")
def command_task(
    task_id: str,
    command: Literal["pause", "resume", "cancel", "takeover"],
    user: Actor,
    db: Db,
    key: Key,
):
    return orchestration_service(db).command(user, task_id, command, key)


@router.post("/tasks/{task_id}/nodes/{node_id}/retry")
def retry_task_node(task_id: str, node_id: str, user: Actor, db: Db, key: Key):
    return orchestration_service(db).retry_node(user, task_id, node_id, key)


@router.post("/tasks/{task_id}/nodes/{node_id}/reconcile")
def reconcile_task_node(
    task_id: str, node_id: str, user: Actor, db: Db, key: Key
):
    return orchestration_service(db).reconcile_node(user, task_id, node_id, key)
