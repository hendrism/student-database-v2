import re
from datetime import datetime, date
from email_validator import validate_email, EmailNotValidError

def validate_student_data(data, is_update=False):
    """Validate student data for creation or update."""
    if not data:
        return "No data provided"
    
    errors = []
    
    # Required fields for creation
    if not is_update:
        required_fields = ['first_name', 'last_name']
        for field in required_fields:
            if not data.get(field) or not data[field].strip():
                errors.append(f"{field.replace('_', ' ').title()} is required")
    
    # Validate name fields
    name_fields = ['first_name', 'last_name', 'preferred_name']
    for field in name_fields:
        value = data.get(field)
        if value and (len(value) > 100 or len(value.strip()) < 1):
            errors.append(f"{field.replace('_', ' ').title()} must be between 1-100 characters")
        if value and not re.match(r"^[a-zA-Z\s\-'\.]+$", value):
            errors.append(f"{field.replace('_', ' ').title()} contains invalid characters")
    
    # Validate pronouns
    pronouns = data.get('pronouns')
    if pronouns and len(pronouns) > 50:
        errors.append("Pronouns must be 50 characters or less")
    
    # Validate grade level
    grade_level = data.get('grade_level')
    valid_grades = ['PK', 'K', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', 'Post-Secondary']
    if grade_level and grade_level not in valid_grades:
        errors.append(f"Grade level must be one of: {', '.join(valid_grades)}")
    
    # Validate monthly services
    monthly_services = data.get('monthly_services')
    if monthly_services is not None:
        if not isinstance(monthly_services, int) or monthly_services < 0 or monthly_services > 50:
            errors.append("Monthly services must be a number between 0-50")
    
    # Validate active status
    active = data.get('active')
    if active is not None and not isinstance(active, bool):
        errors.append("Active status must be true or false")
    
    return errors[0] if errors else None

def validate_goal_data(data, is_update=False):
    """Validate goal data for creation or update."""
    if not data:
        return "No data provided"
    
    errors = []
    
    # Required fields
    if not is_update and not data.get('description'):
        errors.append("Description is required")
    
    # Validate description
    description = data.get('description')
    if description and len(description) > 1000:
        errors.append("Description must be 1000 characters or less")
    
    # Validate completion criteria
    completion_criteria = data.get('completion_criteria')
    if completion_criteria and len(completion_criteria) > 1000:
        errors.append("Completion criteria must be 1000 characters or less")
    
    # Validate target date
    target_date = data.get('target_date')
    if target_date:
        try:
            if isinstance(target_date, str):
                datetime.strptime(target_date, '%Y-%m-%d')
        except ValueError:
            errors.append("Target date must be in YYYY-MM-DD format")
    
    return errors[0] if errors else None

def validate_objective_data(data, is_update=False):
    """Validate objective data for creation or update."""
    if not data:
        return "No data provided"
    
    errors = []
    
    # Required fields
    if not is_update and not data.get('description'):
        errors.append("Description is required")
    
    # Validate description
    description = data.get('description')
    if description and len(description) > 1000:
        errors.append("Description must be 1000 characters or less")
    
    # Validate accuracy target
    accuracy_target = data.get('accuracy_target')
    if accuracy_target and len(accuracy_target) > 50:
        errors.append("Accuracy target must be 50 characters or less")
    
    # Validate notes
    notes = data.get('notes')
    if notes and len(notes) > 2000:
        errors.append("Notes must be 2000 characters or less")
    
    return errors[0] if errors else None

def validate_session_data(data, is_update=False):
    """Validate session data for creation or update."""
    if not data:
        return "No data provided"
    
    errors = []
    
    # Required fields for creation
    if not is_update:
        required_fields = ['student_id', 'session_date']
        for field in required_fields:
            if field not in data or data[field] is None:
                errors.append(f"{field.replace('_', ' ').title()} is required")
    
    # Validate session date
    session_date = data.get('session_date')
    if session_date:
        try:
            if isinstance(session_date, str):
                parsed_date = datetime.strptime(session_date, '%Y-%m-%d').date()
                if parsed_date > date.today():
                    errors.append("Session date cannot be in the future")
        except ValueError:
            errors.append("Session date must be in YYYY-MM-DD format")
    
    # Validate duration
    duration_minutes = data.get('duration_minutes')
    if duration_minutes is not None:
        if not isinstance(duration_minutes, int) or duration_minutes < 1 or duration_minutes > 480:
            errors.append("Duration must be between 1-480 minutes")
    
    # Validate session type
    session_type = data.get('session_type')
    valid_types = ['Individual', 'Group', 'Consultation', 'Assessment', 'Other']
    if session_type and session_type not in valid_types:
        errors.append(f"Session type must be one of: {', '.join(valid_types)}")
    
    # Validate notes
    notes = data.get('notes')
    if notes and len(notes) > 5000:
        errors.append("Notes must be 5000 characters or less")
    
    return errors[0] if errors else None

def validate_trial_log_data(data, is_update=False):
    """Validate trial log data for creation or update."""
    if not data:
        return "No data provided"
    
    errors = []
    
    # Required fields
    if not is_update:
        required_fields = ['objective_id', 'session_date']
        for field in required_fields:
            if field not in data or data[field] is None:
                errors.append(f"{field.replace('_', ' ').title()} is required")
    
    # Validate trial counts
    trial_fields = ['independent', 'verbal', 'gestural', 'physical', 'no_response']
    for field in trial_fields:
        value = data.get(field)
        if value is not None:
            if not isinstance(value, int) or value < 0 or value > 100:
                errors.append(f"{field.replace('_', ' ').title()} must be between 0-100")
    
    # Validate accuracy percentage
    accuracy_percent = data.get('accuracy_percent')
    if accuracy_percent is not None:
        if not isinstance(accuracy_percent, (int, float)) or accuracy_percent < 0 or accuracy_percent > 100:
            errors.append("Accuracy percentage must be between 0-100")
    
    # Validate session date
    session_date = data.get('session_date')
    if session_date:
        try:
            if isinstance(session_date, str):
                parsed_date = datetime.strptime(session_date, '%Y-%m-%d').date()
                if parsed_date > date.today():
                    errors.append("Session date cannot be in the future")
        except ValueError:
            errors.append("Session date must be in YYYY-MM-DD format")
    
    # Validate notes
    notes = data.get('notes')
    if notes and len(notes) > 2000:
        errors.append("Notes must be 2000 characters or less")
    
    return errors[0] if errors else None

def validate_soap_data(data, is_update=False):
    """Validate SOAP note data for creation or update."""
    if not data:
        return "No data provided"
    
    errors = []
    
    # Required fields
    if not is_update:
        required_fields = ['student_id', 'session_date']
        for field in required_fields:
            if field not in data or data[field] is None:
                errors.append(f"{field.replace('_', ' ').title()} is required")
    
    # Validate SOAP sections
    soap_sections = ['subjective', 'objective', 'assessment', 'plan']
    for section in soap_sections:
        value = data.get(section)
        if value and len(value) > 2000:
            errors.append(f"{section.title()} section must be 2000 characters or less")
    
    # Validate session date
    session_date = data.get('session_date')
    if session_date:
        try:
            if isinstance(session_date, str):
                parsed_date = datetime.strptime(session_date, '%Y-%m-%d').date()
                if parsed_date > date.today():
                    errors.append("Session date cannot be in the future")
        except ValueError:
            errors.append("Session date must be in YYYY-MM-DD format")
    
    return errors[0] if errors else None

def validate_user_data(data, is_update=False):
    """Validate user data for registration or update."""
    if not data:
        return "No data provided"
    
    errors = []
    
    # Required fields for registration
    if not is_update:
        required_fields = ['username', 'email', 'password', 'full_name']
        for field in required_fields:
            if not data.get(field) or not data[field].strip():
                errors.append(f"{field.replace('_', ' ').title()} is required")
    
    # Validate username
    username = data.get('username')
    if username:
        if len(username) < 3 or len(username) > 50:
            errors.append("Username must be between 3-50 characters")
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            errors.append("Username can only contain letters, numbers, and underscores")
    
    # Validate email
    email = data.get('email')
    if email:
        try:
            validate_email(email)
        except EmailNotValidError:
            errors.append("Please enter a valid email address")
    
    # Validate password (only for new users or password changes)
    password = data.get('password')
    if password:
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long")
        if not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")
        if not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")
        if not re.search(r'\d', password):
            errors.append("Password must contain at least one number")
    
    # Validate full name
    full_name = data.get('full_name')
    if full_name:
        if len(full_name) > 100:
            errors.append("Full name must be 100 characters or less")
        if not re.match(r"^[a-zA-Z\s\-'\.]+$", full_name):
            errors.append("Full name contains invalid characters")
    
    # Validate role
    role = data.get('role')
    valid_roles = ['admin', 'teacher', 'viewer']
    if role and role not in valid_roles:
        errors.append(f"Role must be one of: {', '.join(valid_roles)}")
    
    return errors[0] if errors else None

def sanitize_input(value):
    """Sanitize input by removing potential harmful characters."""
    if not isinstance(value, str):
        return value
    
    # Remove potential SQL injection characters
    dangerous_chars = ['<', '>', '"', "'", '&', ';']
    for char in dangerous_chars:
        value = value.replace(char, '')
    
    return value.strip()

def validate_date_range(start_date, end_date):
    """Validate that end_date is after start_date."""
    try:
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        if start_date > end_date:
            return "End date must be after start date"
        
        return None
    except ValueError:
        return "Invalid date format. Use YYYY-MM-DD"
