"""
Admin API endpoints for configuration management.
"""
from flask import Blueprint, current_app, jsonify, request
from functools import wraps


admin_bp = Blueprint("admin", __name__)


def require_admin_token(f):
    """Decorator to require admin token for admin endpoints."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get("Authorization")
        expected_token = current_app.config.get("ADMIN_TOKEN", "admin-token")
        if not token or token != f"Bearer {expected_token}":
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.get("/config")
@require_admin_token
def get_config():
    """Get current configuration (without sensitive values)."""
    return jsonify({
        "openai_model": current_app.config.get("OPENAI_MODEL"),
        "chassis_api_configured": bool(
            current_app.config.get("CHASSIS_API_BASE_URL")
            and current_app.config.get("CHASSIS_API_KEY")
        ),
        "whatsapp_configured": bool(
            current_app.config.get("META_ACCESS_TOKEN")
            and current_app.config.get("META_PHONE_NUMBER_ID")
        ),
        "openai_configured": bool(current_app.config.get("OPENAI_API_KEY")),
    })


@admin_bp.get("/stats")
@require_admin_token
def get_stats():
    """Get basic statistics."""
    from ..extensions import db
    from ..models import Lead, Part, Vehicle

    return jsonify({
        "total_parts": db.session.query(Part).count(),
        "total_vehicles": db.session.query(Vehicle).count(),
        "total_leads": db.session.query(Lead).count(),
        "new_leads": db.session.query(Lead).filter_by(status="new").count(),
        "assigned_leads": db.session.query(Lead).filter_by(status="assigned").count(),
    })

