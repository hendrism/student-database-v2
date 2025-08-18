"""Basic API routes for Student Database v2.0."""

from flask import Blueprint, jsonify, request
from datetime import datetime
from models import db, User, Student

# Create blueprints
api_bp = Blueprint('api', __name__, url_prefix='/api/v1')
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

def register_blueprints(app):
    """Register all blueprints with the Flask app."""
    app.register_blueprint(api_bp)
    app.register_blueprint(auth_bp)

# Health check endpoint
@api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    try:
        # Test database connection with a simple query
        db.session.execute(db.text('SELECT 1'))
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '2.0.0'
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': 'Database connection failed',
            'timestamp': datetime.utcnow().isoformat()
        }), 503

# Basic authentication endpoint
@auth_bp.route('/login', methods=['POST'])
def login():
    """Basic login endpoint."""
    data = request.get_json()
    
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Username and password required'}), 400
    
    user = User.query.filter_by(username=data['username']).first()
    
    if user and user.check_password(data['password']):
        token = user.generate_token()
        return jsonify({
            'access_token': token,
            'user': user.to_dict()
        })
    
    return jsonify({'error': 'Invalid credentials'}), 401

# Basic student endpoints
@api_bp.route('/students', methods=['GET'])
def get_students():
    """Get all students."""
    students = Student.query.all()
    return jsonify([student.to_dict() for student in students])

@api_bp.route('/students', methods=['POST'])
def create_student():
    """Create a new student."""
    data = request.get_json()
    
    if not data or not data.get('first_name') or not data.get('last_name'):
        return jsonify({'error': 'First name and last name required'}), 400
    
    student = Student(
        first_name=data['first_name'],
        last_name=data['last_name'],
        email=data.get('email'),
        grade_level=data.get('grade_level')
    )
    
    student.generate_student_id()
    
    try:
        db.session.add(student)
        db.session.commit()
        return jsonify(student.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@api_bp.route('/students/<int:student_id>', methods=['GET'])
def get_student(student_id):
    """Get a specific student."""
    student = Student.query.get_or_404(student_id)
    return jsonify(student.to_dict())

@api_bp.route('/students/<int:student_id>', methods=['PUT'])
def update_student(student_id):
    """Update a student."""
    student = Student.query.get_or_404(student_id)
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    # Update allowed fields
    allowed_fields = ['first_name', 'last_name', 'email', 'phone', 'grade_level', 
                     'emergency_contact_name', 'emergency_contact_phone', 
                     'emergency_contact_relationship', 'diagnosis']
    
    for field in allowed_fields:
        if field in data:
            setattr(student, field, data[field])
    
    try:
        db.session.commit()
        return jsonify(student.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@api_bp.route('/students/<int:student_id>', methods=['DELETE'])
def delete_student(student_id):
    """Delete a student."""
    student = Student.query.get_or_404(student_id)
    
    try:
        db.session.delete(student)
        db.session.commit()
        return jsonify({'message': 'Student deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    