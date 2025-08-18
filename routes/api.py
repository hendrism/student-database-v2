from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from extensions import db
from models import Student, Goal, Objective, TrialLog, Session
from sqlalchemy import text

api_bp = Blueprint('api', __name__)

# Health check endpoint
@api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    try:
        # Check database connection
        db.session.execute(text('SELECT 1'))
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '2.0.0'
        })
    except Exception as e:
        current_app.logger.error(f'Health check failed: {str(e)}')
        return jsonify({
            'status': 'unhealthy',
            'error': 'Database connection failed',
            'timestamp': datetime.utcnow().isoformat()
        }), 503

# Students API
@api_bp.route('/students', methods=['GET'])
def get_students():
    """Get all students."""
    try:
        students = Student.query.filter(Student.active == True).all()
        students_data = [student.to_dict() for student in students]
        
        return jsonify({
            'students': students_data,
            'total': len(students_data)
        })
        
    except Exception as e:
        current_app.logger.error(f'Error retrieving students: {str(e)}')
        return jsonify({'error': 'Failed to retrieve students'}), 500

@api_bp.route('/students', methods=['POST'])
def create_student():
    """Create a new student."""
    try:
        data = request.json
        
        # Basic validation
        if not data.get('first_name') or not data.get('last_name'):
            return jsonify({'error': 'First name and last name are required'}), 400
        
        # Create new student
        student = Student(
            first_name=data['first_name'],
            last_name=data['last_name'],
            preferred_name=data.get('preferred_name'),
            pronouns=data.get('pronouns'),
            grade_level=data.get('grade_level'),
            monthly_services=data.get('monthly_services')
        )
        
        db.session.add(student)
        db.session.commit()
        
        current_app.logger.info(f'Created new student: {student.display_name}')
        
        return jsonify({
            'message': 'Student created successfully',
            'student': student.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error creating student: {str(e)}')
        return jsonify({'error': 'Failed to create student'}), 500

@api_bp.route('/students/<int:student_id>', methods=['GET'])
def get_student(student_id):
    """Get a specific student by ID."""
    try:
        student = Student.query.get_or_404(student_id)
        return jsonify(student.to_dict())
        
    except Exception as e:
        current_app.logger.error(f'Error retrieving student {student_id}: {str(e)}')
        return jsonify({'error': 'Failed to retrieve student'}), 500

# Simple dashboard analytics
@api_bp.route('/analytics/dashboard', methods=['GET'])
def get_dashboard_analytics():
    """Get dashboard analytics data."""
    try:
        total_students = Student.query.filter(Student.active == True).count()
        total_goals = Goal.query.filter(Goal.active == True).count()
        
        return jsonify({
            'stats': {
                'total_students': total_students,
                'total_goals': total_goals,
                'sessions_this_week': 0,  # Placeholder
                'completion_rate': 95    # Placeholder
            },
            'recent_activity': []
        })
        
    except Exception as e:
        current_app.logger.error(f'Error retrieving dashboard analytics: {str(e)}')
        return jsonify({'error': 'Failed to retrieve analytics'}), 500
    