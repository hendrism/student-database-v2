from flask import Blueprint, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from auth.decorators import token_required, role_required
from models import db, Student, Goal, Objective
from utils.validators import validate_student_data
import logging

logger = logging.getLogger(__name__)
students_bp = Blueprint('students', __name__, url_prefix='/api/students')

@students_bp.route('/', methods=['GET'])
@token_required
def get_all_students():
    """Get all students with pagination and filtering."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        active_only = request.args.get('active', 'true').lower() == 'true'
        include_sensitive = request.args.get('include_sensitive', 'true').lower() == 'true'
        
        query = Student.query
        
        if active_only:
            query = query.filter(Student.active == True)
        
        # Add search functionality
        search = request.args.get('search', '').strip()
        if search:
            query = query.filter(
                db.or_(
                    Student.first_name.ilike(f'%{search}%'),
                    Student.last_name.ilike(f'%{search}%'),
                    Student.preferred_name.ilike(f'%{search}%')
                )
            )
        
        # Add grade filter
        grade = request.args.get('grade')
        if grade:
            query = query.filter(Student.grade_level == grade)
        
        students = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        return jsonify({
            'students': [student.to_dict(include_sensitive=include_sensitive) 
                        for student in students.items],
            'pagination': {
                'page': page,
                'pages': students.pages,
                'per_page': per_page,
                'total': students.total,
                'has_next': students.has_next,
                'has_prev': students.has_prev
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error retrieving students: {e}")
        return jsonify({'error': 'Failed to retrieve students'}), 500

@students_bp.route('/<int:student_id>', methods=['GET'])
@token_required
def get_student(student_id):
    """Get a specific student by ID."""
    try:
        include_sensitive = request.args.get('include_sensitive', 'true').lower() == 'true'
        
        student = Student.query.get_or_404(student_id)
        return jsonify(student.to_dict(include_sensitive=include_sensitive)), 200
        
    except Exception as e:
        logger.error(f"Error retrieving student {student_id}: {e}")
        return jsonify({'error': 'Student not found'}), 404

@students_bp.route('/', methods=['POST'])
@token_required
@role_required(['admin', 'teacher'])
def create_student():
    """Create a new student."""
    try:
        data = request.get_json()
        
        # Validate required fields
        validation_error = validate_student_data(data)
        if validation_error:
            return jsonify({'error': validation_error}), 400
        
        # Check for duplicate names (optional business rule)
        existing = Student.query.filter(
            Student.first_name == data.get('first_name'),
            Student.last_name == data.get('last_name'),
            Student.active == True
        ).first()
        
        if existing:
            logger.warning(f"Attempted to create duplicate student: {data.get('first_name')} {data.get('last_name')}")
        
        student = Student(
            first_name=data.get('first_name'),
            last_name=data.get('last_name'),
            preferred_name=data.get('preferred_name'),
            pronouns=data.get('pronouns'),
            grade_level=data.get('grade_level'),
            monthly_services=data.get('monthly_services', 0)
        )
        
        db.session.add(student)
        db.session.commit()
        
        logger.info(f"Created new student: {student.display_name} (ID: {student.id})")
        return jsonify(student.to_dict()), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating student: {e}")
        return jsonify({'error': 'Failed to create student'}), 500

@students_bp.route('/<int:student_id>', methods=['PUT'])
@token_required
@role_required(['admin', 'teacher'])
def update_student(student_id):
    """Update an existing student."""
    try:
        student = Student.query.get_or_404(student_id)
        data = request.get_json()
        
        # Validate data
        validation_error = validate_student_data(data, is_update=True)
        if validation_error:
            return jsonify({'error': validation_error}), 400
        
        # Update allowed fields
        updatable_fields = [
            'first_name', 'last_name', 'preferred_name', 'pronouns',
            'grade_level', 'monthly_services', 'active'
        ]
        
        for field in updatable_fields:
            if field in data:
                setattr(student, field, data[field])
        
        db.session.commit()
        
        logger.info(f"Updated student: {student.display_name} (ID: {student.id})")
        return jsonify(student.to_dict()), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating student {student_id}: {e}")
        return jsonify({'error': 'Failed to update student'}), 500

@students_bp.route('/<int:student_id>', methods=['DELETE'])
@token_required
@role_required(['admin'])
def delete_student(student_id):
    """Soft delete a student (mark as inactive)."""
    try:
        student = Student.query.get_or_404(student_id)
        
        # Soft delete - just mark as inactive
        student.active = False
        db.session.commit()
        
        logger.info(f"Soft deleted student: {student.display_name} (ID: {student.id})")
        return jsonify({'message': 'Student deactivated successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting student {student_id}: {e}")
        return jsonify({'error': 'Failed to delete student'}), 500

@students_bp.route('/<int:student_id>/goals', methods=['GET'])
@token_required
def get_student_goals(student_id):
    """Get all goals for a specific student."""
    try:
        student = Student.query.get_or_404(student_id)
        active_only = request.args.get('active', 'true').lower() == 'true'
        
        query = Goal.query.filter(Goal.student_id == student_id)
        if active_only:
            query = query.filter(Goal.active == True)
        
        goals = query.order_by(Goal.created_at.desc()).all()
        
        return jsonify({
            'student_id': student_id,
            'student_name': student.display_name,
            'goals': [goal.to_dict() for goal in goals]
        }), 200
        
    except Exception as e:
        logger.error(f"Error retrieving goals for student {student_id}: {e}")
        return jsonify({'error': 'Failed to retrieve student goals'}), 500

@students_bp.route('/<int:student_id>/goals', methods=['POST'])
@token_required
@role_required(['admin', 'teacher'])
def create_student_goal(student_id):
    """Create a new goal for a specific student."""
    try:
        student = Student.query.get_or_404(student_id)
        data = request.get_json()
        
        if not data.get('description'):
            return jsonify({'error': 'Goal description is required'}), 400
        
        goal = Goal(
            student_id=student_id,
            description=data.get('description'),
            completion_criteria=data.get('completion_criteria'),
            target_date=data.get('target_date')
        )
        
        db.session.add(goal)
        db.session.commit()
        
        logger.info(f"Created goal for student {student.display_name}: {goal.description}")
        return jsonify(goal.to_dict()), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating goal for student {student_id}: {e}")
        return jsonify({'error': 'Failed to create goal'}), 500

@students_bp.route('/<int:student_id>/anonymize', methods=['POST'])
@token_required
@role_required(['admin'])
def anonymize_student(student_id):
    """Anonymize a student's data for privacy compliance."""
    try:
        student = Student.query.get_or_404(student_id)
        
        if student.anonymized:
            return jsonify({'message': 'Student is already anonymized'}), 200
        
        student.anonymize()
        db.session.commit()
        
        logger.info(f"Anonymized student data: ID {student_id}")
        return jsonify({
            'message': 'Student data anonymized successfully',
            'student': student.to_dict(include_sensitive=False)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error anonymizing student {student_id}: {e}")
        return jsonify({'error': 'Failed to anonymize student'}), 500

@students_bp.route('/stats', methods=['GET'])
@token_required
def get_students_stats():
    """Get overall statistics about students."""
    try:
        total_students = Student.query.count()
        active_students = Student.query.filter(Student.active == True).count()
        anonymized_students = Student.query.filter(Student.anonymized == True).count()
        
        # Grade level distribution
        grade_stats = db.session.query(
            Student.grade_level,
            db.func.count(Student.id).label('count')
        ).filter(Student.active == True).group_by(Student.grade_level).all()
        
        return jsonify({
            'total_students': total_students,
            'active_students': active_students,
            'inactive_students': total_students - active_students,
            'anonymized_students': anonymized_students,
            'grade_distribution': {grade: count for grade, count in grade_stats if grade}
        }), 200
        
    except Exception as e:
        logger.error(f"Error retrieving student statistics: {e}")
        return jsonify({'error': 'Failed to retrieve statistics'}), 500