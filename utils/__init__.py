"""
Utility modules for the Student Database application.

This package contains utilities for:
- Data validation and sanitization
- Report generation and analytics 
- Privacy and data protection
- Database backup and restore operations
"""

from .validators import (
    validate_student_data,
    validate_goal_data, 
    validate_objective_data,
    validate_session_data,
    validate_trial_log_data,
    validate_soap_data,
    validate_user_data,
    validate_date_range,
    sanitize_input
)

# Reports module imports are handled individually due to optional pandas dependency
# Import from utils.reports directly when needed

from .privacy import (
    PrivacyManager,
    privacy_required,
    PRIVACY_CONFIG
)

from .backup import (
    DatabaseBackup
)

__all__ = [
    # Validators
    'validate_student_data',
    'validate_goal_data', 
    'validate_objective_data',
    'validate_session_data',
    'validate_trial_log_data',
    'validate_soap_data',
    'validate_user_data',
    'validate_date_range',
    'sanitize_input',
    
    # Privacy
    'PrivacyManager',
    'privacy_required',
    'PRIVACY_CONFIG',
    
    # Backup
    'DatabaseBackup'
    
    # Note: Report functions are imported directly from utils.reports due to optional dependencies
]
