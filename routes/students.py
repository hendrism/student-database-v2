from flask import Blueprint, request, jsonify
from marshmallow import Schema, fields, ValidationError, validate
from extensions import db
from models import Student, Goal, Objective
from auth.decorators import require_auth, require_permission

students_bp = Blueprint('students', __name__, url_prefix='/api/students')

class StudentCreateSchema(Schema):
    first_name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    last_name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    preferred_name = fields.Str(validate=validate.Length(max=100), allow_none=True)
    pronouns = fields.Str(validate=validate.Length(max=50), allow_none=True)
    grade_level = fields.Str(validate=validate.OneOf([
        'Grade 9', 'Grade 10', 'Grade 11', 'Grade 12'
    ]))
    monthly_services = fields.Int(validate=validate.Range(min=1, max=20))

@students_bp.route('/', methods=['GET'])
@require_auth
def get_students():
    """Get all students with pagination."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    students = Student.query.filter_by(active=True).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'students': [s.to_dict() for s in students.items],
        'total': students.total,
        'page': page,
        'pages': students.pages
    })

@students_bp.route('/', methods=['POST'])
@require_auth
@require_permission('write')
def create_student():
    """Create a new student."""
    schema = StudentCreateSchema()
    try:
        data = schema.load(request.json)
        student = Student(**data)
        db.session.add(student)
        db.session.commit()
        return jsonify(student.to_dict()), 201
    except ValidationError as e:
        return jsonify({'error': 'Validation failed', 'messages': e.messages}), 400

@students_bp.route('/<int:student_id>', methods=['GET'])
@require_auth
def get_student(student_id):
    """Get a specific student."""
    student = Student.query.get_or_404(student_id)
    return jsonify(student.to_dict())

@students_bp.route('/<int:student_id>', methods=['PUT'])
@require_auth
@require_permission('write')
def update_student(student_id):
    """Update a student."""
    student = Student.query.get_or_404(student_id)
    data = request.json
    
    for key, value in data.items():
        if hasattr(student, key):
            setattr(student, key, value)
    
    db.session.commit()
    return jsonify(student.to_dict())

@students_bp.route('/<int:student_id>', methods=['DELETE'])
@require_auth
@require_permission('delete')
def delete_student(student_id):
    """Soft delete a student."""
    student = Student.query.get_or_404(student_id)
    student.active = False
    db.session.commit()
    return '', 204