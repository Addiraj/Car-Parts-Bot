import hmac
import json
import hashlib
from typing import Any
from flask import Blueprint, current_app, jsonify, request
import requests
from ..extensions import db
from ..models import Lead, Part, Vehicle
from ..services.gpt_service import GPTService
from ..services.chassis_service import ChassisService
from ..services.lead_service import LeadService
from ..services.carparts_dubai_service import CarPartsDubaiService
from sqlalchemy import or_, and_

whatsapp_bp = Blueprint("whatsapp", __name__)

@whatsapp_bp.get("")
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == current_app.config.get("META_VERIFY_TOKEN"):
        return challenge, 200
    return "Forbidden", 403


@whatsapp_bp.post("")
def receive_message():
    payload: dict[str, Any] = request.get_json(silent=True) or {}

    entries = payload.get("entry", [])
    for entry in entries:
        for change in entry.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])
            contacts = value.get("contacts", [])
            user_id = contacts[0]["wa_id"] if contacts else None

            for msg in messages:
                text = None
                if msg.get("type") == "text":
                    text = msg.get("text", {}).get("body")

                if user_id and text:
                    # Process message with GPT and search
                    response_text = _process_user_message(user_id, text)

                    # Send response
                    _send_whatsapp_text(user_id, response_text)

    return jsonify({"status": "ok"})


def _process_user_message(user_id: str, message: str) -> str:
    """Process user message: extract intent, search, format response."""
    try:
        # Initialize services
        gpt_service = GPTService()
        chassis_service = ChassisService()
        lead_service = LeadService()

        # Extract intent using GPT
        intent_data = gpt_service.extract_intent(message)
        intent = intent_data.get("intent", "unknown")
        entities = intent_data.get("entities", {})
        language = intent_data.get("language", "en")

        # Create lead
        lead = lead_service.create_lead(user_id, message, intent)

        # Handle greetings
        if intent == "greeting":
            if language == "ar":
                return "مرحباً! كيف يمكنني مساعدتك في البحث عن قطع الغيار اليوم؟"
            return "Hello! How can I help you find car parts today?"

        # Search based on intent
        search_results = []

        if intent == "part_number":
            part_number = entities.get("part_number") or message.strip()
            parts = (
                db.session.query(Part)
                .filter(Part.part_number.ilike(f"%{part_number}%"))
                .limit(10)
                .all()
            )
            search_results = [_serialize_part(p) for p in parts]
            if not search_results:
                external_service = CarPartsDubaiService()
                search_results = external_service.find_by_part_number(part_number)

        elif intent == "chassis":
            chassis_number = entities.get("chassis") or message.strip()
            # Lookup vehicle via external API
            vehicle_data = chassis_service.lookup_vehicle(chassis_number)

            if vehicle_data:
                # Find parts for this vehicle
                vehicle = (
                    db.session.query(Vehicle)
                    .filter_by(chassis_number=vehicle_data["chassis_number"])
                    .first()
                )
                if vehicle:
                    parts = (
                        db.session.query(Part)
                        .filter(Part.vehicle_id == vehicle.id)
                        .limit(10)
                        .all()
                    )
                    search_results = [_serialize_part(p) for p in parts]
            else:
                # No vehicle found
                if language == "ar":
                    return "عذراً، لم نتمكن من العثور على معلومات السيارة لهذا الرقم. يرجى التحقق من الرقم والمحاولة مرة أخرى."
                return "Sorry, we couldn't find vehicle information for this chassis number. Please verify the number and try again."

        elif intent == "car_part":
            car_make = entities.get("car_make", "")
            car_model = entities.get("car_model", "")
            part_name = entities.get("part_name", "")

            # Build search query
            if car_make or car_model:
                car_query = f"{car_make} {car_model}".strip()
            else:
                # Try to extract from message
                car_query = message

            if not part_name:
                # Try to extract part name from message
                part_name = message

            # Search
            make_model = [s.strip() for s in car_query.split(" ") if s.strip()]
            vehicle_filters = []
            if make_model:
                vehicle_filters.append(
                    or_(
                        Vehicle.make.ilike(f"%{make_model[0]}%"),
                        Vehicle.model.ilike(f"%{make_model[0]}%"),
                    )
                )
            if len(make_model) > 1:
                vehicle_filters.append(
                    or_(
                        Vehicle.make.ilike(f"%{make_model[1]}%"),
                        Vehicle.model.ilike(f"%{make_model[1]}%"),
                    )
                )

            vehicles = (
                db.session.query(Vehicle).filter(and_(*vehicle_filters))
                if vehicle_filters
                else db.session.query(Vehicle)
            )

            parts = (
                db.session.query(Part)
                .join(Vehicle, Part.vehicle_id == Vehicle.id, isouter=True)
                .filter(
                    and_(
                        Part.name.ilike(f"%{part_name}%"),
                        or_(
                            Vehicle.id.in_([v.id for v in vehicles.all()]),
                            Vehicle.id.is_(None),
                        ),
                    )
                )
                .limit(10)
                .all()
            )
            search_results = [_serialize_part(p) for p in parts]

        # Format response using GPT
        response = gpt_service.format_response(search_results, intent, language)

        # Update lead with results
        lead.status = "responded"
        db.session.commit()

        return response

    except Exception as e:
        current_app.logger.error(f"Error processing message: {e}")
        return "Sorry, we encountered an error. Please try again later."


def _serialize_part(p: Part) -> dict:
    """Serialize Part model to dict."""
    return {
        "id": p.id,
        "part_number": p.part_number,
        "name": p.name,
        "brand": p.brand,
        "price": float(p.price) if p.price is not None else None,
        "quantity_min": p.quantity_min,
        "vehicle": _serialize_vehicle(p.vehicle) if p.vehicle else None,
    }


def _serialize_vehicle(v: Vehicle | None) -> dict | None:
    """Serialize Vehicle model to dict."""
    if not v:
        return None
    return {
        "id": v.id,
        "make": v.make,
        "model": v.model,
        "year": v.year,
        "chassis_number": v.chassis_number,
    }


def _send_whatsapp_text(wa_id: str, text: str) -> None:
    token = current_app.config.get("META_ACCESS_TOKEN")
    phone_id = current_app.config.get("META_PHONE_NUMBER_ID")
    if not token or not phone_id:
        return

    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    data = {
        "messaging_product": "whatsapp",
        "to": wa_id,
        "type": "text",
        "text": {"body": text},
    }
    try:
        requests.post(url, headers=headers, json=data, timeout=10)
    except Exception:
        pass


