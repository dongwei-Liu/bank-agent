from fastapi import APIRouter, Query, Response

from api.context import Actor, Db, Key, DecimalRoute, card_service
from schemas.banking import (
    CardAliasRequest,
    CardApplicationRequest,
    CardControlsRequest,
)

router = APIRouter(prefix="/api/cards", tags=["cards"], route_class=DecimalRoute)


@router.get("")
def list_cards(user: Actor, db: Db):
    return card_service(db).list(user)


@router.post("", status_code=201)
def apply_for_card(body: CardApplicationRequest, user: Actor, db: Db, key: Key):
    return card_service(db).request_application(user, body, key)


@router.get("/{card_id}")
def get_card(card_id: str, user: Actor, db: Db):
    return card_service(db).detail(user, card_id)


@router.patch("/{card_id}")
def rename_card(card_id: str, body: CardAliasRequest, user: Actor, db: Db):
    return card_service(db).rename(user, card_id, body.alias)


@router.post("/{card_id}/activate", status_code=201)
def activate_card(card_id: str, user: Actor, db: Db, key: Key):
    return card_service(db).request_activation(user, card_id, key)


@router.post("/{card_id}/reveal", status_code=201)
def request_card_number_reveal(card_id: str, user: Actor, db: Db, key: Key):
    return card_service(db).request_reveal(user, card_id, key)


@router.get("/{card_id}/reveal")
def reveal_card_number(
    card_id: str,
    user: Actor,
    db: Db,
    response: Response,
    action_id: str = Query(min_length=1, max_length=36),
):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return card_service(db).reveal_number(user, card_id, action_id)


@router.post("/{card_id}/limits", status_code=201)
def change_card_controls(
    card_id: str, body: CardControlsRequest, user: Actor, db: Db, key: Key
):
    return card_service(db).request_controls(user, card_id, body, key)


@router.post("/{card_id}/lock", status_code=201)
def lock_card(card_id: str, user: Actor, db: Db, key: Key):
    return card_service(db).request_state(user, card_id, "lock", key)


@router.post("/{card_id}/unlock", status_code=201)
def unlock_card(card_id: str, user: Actor, db: Db, key: Key):
    return card_service(db).request_state(user, card_id, "unlock", key)


@router.post("/{card_id}/report-lost", status_code=201)
def report_lost_card(card_id: str, user: Actor, db: Db, key: Key):
    return card_service(db).request_state(user, card_id, "report-lost", key)


@router.post("/{card_id}/replace", status_code=201)
def replace_card(card_id: str, user: Actor, db: Db, key: Key):
    return card_service(db).request_state(user, card_id, "replace", key)
