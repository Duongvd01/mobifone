from extensions import db
from flask_login import UserMixin

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(256), nullable=False)
from app import db
from datetime import datetime

class TranscriptionHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150))  # hoặc ForeignKey nếu muốn liên kết user
    filename = db.Column(db.String(255))
    transcript = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
