# auth/routes.py - FIXED VERSION
from flask import Blueprint, request, jsonify, current_app, g
from marshmallow import Schema, fields, ValidationError, validate
from datetime import datetime
from models import db  # Import from models, not local
from .models import User  # Import User from local auth.models
import re

# Create the auth blueprint HERE, not import it
auth_bp = Blueprint('auth', __name__)

# Validation schemas
class LoginSchema(Schema):
    username = fields.Str(required=True, validate=validate.Length(min=3, max=80))
    password = fields.Str(required=True, validate=validate.Length(min=8, max=128))

class RegisterSchema(Schema):
    username = fields.Str(required=True, validate=validate.Length(min=3, max=80))
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=8, max=128))
    first_name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    last_name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    role = fields.Str(validate=validate.OneOf(['clinician', 'intern', 'admin']), missing='clinician')

def validate_password_strength(password):
    """Validate password meets security requirements."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    
    return True, "Password is valid"

@auth_bp.route('/login', methods=['POST'])
def login():
    """User login endpoint."""
    try:
        schema = LoginSchema()
        data = schema.load(request.json)
        
        username = data['username']
        password = data['password']
        
        # Find user
        user = User.query.filter_by(username=username).first()
        
        if not user:
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Check if account is locked
        if user.is_locked():
            return jsonify({'error': 'Account is temporarily locked'}), 423
        
        # Check if account is active
        if not user.active:
            return jsonify({'error': 'Account is deactivated'}), 403
        
        # Verify password
        if not user.check_password(password):
            user.failed_login_attempts += 1
            
            # Lock account after 5 failed attempts
            if user.failed_login_attempts >= 5:
                user.lock_account()
                db.session.commit()
                return jsonify({'error': 'Account locked due to too many failed attempts'}), 423
            
            db.session.commit()
            return jsonify({
                'error': 'Invalid credentials',
                'attempts_remaining': 5 - user.failed_login_attempts
            }), 401
        
        # Successful login
        user.unlock_account()  # Reset failed attempts
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Generate tokens
        access_token = user.generate_access_token()
        refresh_token = user.generate_refresh_token()
        
        current_app.logger.info(f'User {username} logged in successfully')
        
        return jsonify({
            'message': 'Login successful',
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': user.to_dict()
        })
        
    except ValidationError as e:
        return jsonify({'error': 'Validation failed', 'messages': e.messages}), 400
    except Exception as e:
        current_app.logger.error(f'Login error: {str(e)}')
        return jsonify({'error': 'Login failed'}), 500

@auth_bp.route('/register', methods=['POST'])
def register():
    """User registration endpoint."""
    try:
        schema = RegisterSchema()
        data = schema.load(request.json)
        
        # Validate password strength
        is_valid, message = validate_password_strength(data['password'])
        if not is_valid:
            return jsonify({'error': message}), 400
        
        # Check if username exists
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Username already exists'}), 409
        
        # Check if email exists
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email already registered'}), 409
        
        # Create new user
        user = User(
            username=data['username'],
            email=data['email'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            role=data['role']
        )
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.commit()
        
        current_app.logger.info(f'New user registered: {user.username}')
        
        return jsonify({
            'message': 'Registration successful',
            'user': user.to_dict()
        }), 201
        
    except ValidationError as e:
        return jsonify({'error': 'Validation failed', 'messages': e.messages}), 400
    except Exception as e:
        current_app.logger.error(f'Registration error: {str(e)}')
        return jsonify({'error': 'Registration failed'}), 500

@auth_bp.route('/profile', methods=['GET'])
def get_profile():
    """Get current user profile."""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Authentication required'}), 401
        
        token = auth_header.split(' ')[1]
        user = User.verify_token(token)
        
        if not user:
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        return jsonify({'user': user.to_dict(include_sensitive=True)})
        
    except Exception as e:
        current_app.logger.error(f'Profile retrieval error: {str(e)}')
        return jsonify({'error': 'Failed to retrieve profile'}), 500

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """User logout endpoint."""
    try:
        # In a stateless JWT system, logout is handled client-side
        # But we can track it for audit purposes
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            user = User.verify_token(token)
            if user:
                current_app.logger.info(f'User {user.username} logged out')
        
        return jsonify({'message': 'Logout successful'})
        
    except Exception as e:
        current_app.logger.error(f'Logout error: {str(e)}')
        return jsonify({'error': 'Logout failed'}), 500

@auth_bp.route('/refresh', methods=['POST'])
def refresh_token():
    """Refresh access token using refresh token."""
    try:
        data = request.json
        if not data or 'refresh_token' not in data:
            return jsonify({'error': 'Refresh token required'}), 400
        
        user = User.verify_refresh_token(data['refresh_token'])
        if not user:
            return jsonify({'error': 'Invalid or expired refresh token'}), 401
        
        # Generate new access token
        new_access_token = user.generate_access_token()
        
        return jsonify({
            'access_token': new_access_token,
            'message': 'Token refreshed successfully'
        })
        
    except Exception as e:
        current_app.logger.error(f'Token refresh error: {str(e)}')
        return jsonify({'error': 'Token refresh failed'}), 500