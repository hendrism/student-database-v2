from flask import Blueprint

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/health', methods=['GET'])
def auth_health():
    """Simple auth health check."""
    return {'status': 'auth module loaded'}