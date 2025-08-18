from functools import wraps
from flask import request, jsonify, g, current_app
from .models import User

# Dev helper: provide a current user when AUTH_DISABLED is on
def _dev_user():
    try:
        # Try to use an existing user from the DB
        u = User.query.first()
        if u:
            return u
    except Exception:
        # DB might not be ready; fall back to a stub
        pass
    class _Stub:
        id = 0
        username = "dev"
        role = "clinician"
        active = True
        def has_permission(self, *_):
            return True
    return _Stub()

def require_auth(f):
    """Decorator to require authentication."""
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Bypass auth in dev mode
        if current_app.config.get("AUTH_DISABLED"):
            if not hasattr(g, 'current_user'):
                g.current_user = _dev_user()
            return f(*args, **kwargs)

        auth_header = request.headers.get('Authorization')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Authentication required'}), 401
        
        token = auth_header.split(' ')[1]
        user = User.verify_token(token)
        
        if not user:
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        g.current_user = user
        return f(*args, **kwargs)
    
    return decorated_function

def require_permission(permission):
    """Decorator to require specific permission."""
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Bypass permission checks in dev mode
            if current_app.config.get("AUTH_DISABLED"):
                if not hasattr(g, 'current_user'):
                    g.current_user = _dev_user()
                return f(*args, **kwargs)

            if not hasattr(g, 'current_user'):
                return jsonify({'error': 'Authentication required'}), 401
            
            if not g.current_user.has_permission(permission):
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def require_role(role):
    """Decorator to require specific role."""
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Bypass role checks in dev mode
            if current_app.config.get("AUTH_DISABLED"):
                if not hasattr(g, 'current_user'):
                    g.current_user = _dev_user()
                return f(*args, **kwargs)

            if not hasattr(g, 'current_user'):
                return jsonify({'error': 'Authentication required'}), 401
            
            if g.current_user.role != role:
                return jsonify({'error': 'Insufficient role'}), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

# Aliases for compatibility with route imports
token_required = require_auth

def role_required(roles):
    """Decorator to require one of the specified roles."""
    if isinstance(roles, str):
        roles = [roles]
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'current_user'):
                return jsonify({'error': 'Authentication required'}), 401
            
            if g.current_user.role not in roles:
                return jsonify({'error': f'Requires one of roles: {", ".join(roles)}'}), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator
