from datetime import datetime, timedelta
from flask import current_app
from werkzeug.security import generate_password_hash, check_password_hash
import jwt

from extensions import db


class User(db.Model):
    """User model for authentication and authorization."""

    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    # Profile information
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    role = db.Column(db.String(50), default='clinician')

    # Account status
    active = db.Column(db.Boolean, default=True)
    email_verified = db.Column(db.Boolean, default=False)

    # Security tracking
    last_login = db.Column(db.DateTime)
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime)
    password_changed_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Audit trail
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def set_password(self, password):
        """Set password hash."""
        self.password_hash = generate_password_hash(password)
        self.password_changed_at = datetime.utcnow()

    def check_password(self, password):
        """Check password against hash."""
        return check_password_hash(self.password_hash, password)

    def is_locked(self):
        """Check if account is locked due to failed attempts."""
        return bool(self.locked_until and self.locked_until > datetime.utcnow())

    def lock_account(self, duration_minutes=30):
        """Lock account for specified duration."""
        self.locked_until = datetime.utcnow() + timedelta(minutes=duration_minutes)
        self.failed_login_attempts += 1

    def unlock_account(self):
        """Unlock account and reset failed attempts."""
        self.locked_until = None
        self.failed_login_attempts = 0

    def generate_access_token(self, expires_delta=None):
        """Generate JWT access token."""
        if expires_delta is None:
            expires_delta = timedelta(hours=1)

        payload = {
            'user_id': self.id,
            'username': self.username,
            'role': self.role,
            'exp': datetime.utcnow() + expires_delta,
            'iat': datetime.utcnow(),
            'type': 'access'
        }

        return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')

    def generate_refresh_token(self):
        """Generate JWT refresh token."""
        payload = {
            'user_id': self.id,
            'exp': datetime.utcnow() + timedelta(days=30),
            'iat': datetime.utcnow(),
            'type': 'refresh'
        }

        return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')

    @staticmethod
    def verify_token(token, token_type='access'):
        """Verify JWT token."""
        try:
            payload = jwt.decode(
                token,
                current_app.config['SECRET_KEY'],
                algorithms=['HS256'],
            )
            if payload.get('type') != token_type:
                return None
            user = User.query.get(payload['user_id'])
            return user if user and user.active else None
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None

    @staticmethod
    def verify_refresh_token(token):
        """Verify a refresh token."""
        return User.verify_token(token, token_type='refresh')

    def has_permission(self, permission):
        """Check if user has specific permission."""
        role_permissions = {
            'admin': ['read', 'write', 'delete', 'admin'],
            'clinician': ['read', 'write'],
            'intern': ['read'],
            'viewer': ['read'],
        }
        return permission in role_permissions.get(self.role, [])

    def to_dict(self, include_sensitive=False):
        """Convert to dictionary."""
        data = {
            'id': self.id,
            'username': self.username,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'role': self.role,
            'active': self.active,
            'email_verified': self.email_verified,
            'last_login': self.last_login.isoformat() if self.last_login else None,
        }
        if include_sensitive:
            data.update({
                'email': self.email,
                'failed_login_attempts': self.failed_login_attempts,
                'locked_until': self.locked_until.isoformat() if self.locked_until else None,
            })
        return data


