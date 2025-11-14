from datetime import datetime
from .extensions import db


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Vehicle(db.Model, TimestampMixin):
    __tablename__ = "vehicles"

    id = db.Column(db.Integer, primary_key=True)
    make = db.Column(db.String(64), index=True, nullable=False)
    model = db.Column(db.String(64), index=True, nullable=False)
    year = db.Column(db.String(16), index=True, nullable=True)
    chassis_number = db.Column(db.String(64), unique=True, index=True, nullable=True)

    parts = db.relationship("Part", back_populates="vehicle", lazy=True)


class Part(db.Model, TimestampMixin):
    __tablename__ = "parts"

    id = db.Column(db.Integer, primary_key=True)
    part_number = db.Column(db.String(128), unique=False, index=True, nullable=False)
    name = db.Column(db.String(256), index=True, nullable=False)
    brand = db.Column(db.String(128), index=True, nullable=True)
    price = db.Column(db.Numeric(12, 2), nullable=True)
    quantity_min = db.Column(db.Integer, nullable=True)

    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=True)
    vehicle = db.relationship("Vehicle", back_populates="parts")


class Lead(db.Model, TimestampMixin):
    __tablename__ = "leads"

    id = db.Column(db.Integer, primary_key=True)
    whatsapp_user_id = db.Column(db.String(64), index=True, nullable=False)
    user_locale = db.Column(db.String(16), nullable=True)
    intent = db.Column(db.String(64), nullable=True)
    query_text = db.Column(db.Text, nullable=True)
    assigned_agent = db.Column(db.String(128), nullable=True)
    status = db.Column(db.String(32), default="new", nullable=False)


