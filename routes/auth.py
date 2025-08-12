from flask import Blueprint

auth_bp = Blueprint('auth', __name__)

# Import all auth routes from the main auth module
from auth.routes import *