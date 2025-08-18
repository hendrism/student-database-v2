from extensions import db

# Import all models so they're available when importing from models
from .student import Student, Goal, Objective
from .session import Session, TrialLog
from .soap import SOAPNote
from auth.models import User

__all__ = [
    'db',
    'Student',
    'Goal',
    'Objective',
    'Session',
    'TrialLog',
    'SOAPNote',
    'User',
]

