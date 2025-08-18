from datetime import datetime, date

from flask import Blueprint, jsonify, request
from marshmallow import Schema, ValidationError, fields, validate

from auth.decorators import require_auth
from extensions import db
from models import Session, Student

sessions_bp = Blueprint('sessions', __name__, url_prefix='/api/sessions')

class SessionSchema(Schema):
    student_id = fields.Int(required=True)
    session_date = fields.Date(required=True)
    start_time = fields.Time(required=True)
    end_time = fields.Time(required=True)
    session_type = fields.Str(validate=validate.OneOf([
        'Individual', 'Group', 'Assessment', 'Consultation'
    ]))
    status = fields.Str(validate=validate.OneOf([
        'Scheduled', 'Completed', 'Cancelled', 'No Show', 'Makeup Needed'
    ]))
    location = fields.Str(validate=validate.Length(max=100))
    notes = fields.Str(validate=validate.Length(max=1000))

@sessions_bp.route('/', methods=['GET'])
@require_auth
def get_sessions():
    """Get sessions with optional filtering."""
    student_id = request.args.get('student_id', type=int)
    start_date = request.args.get('start_date', type=lambda x: datetime.strptime(x, '%Y-%m-%d').date())
    end_date = request.args.get('end_date', type=lambda x: datetime.strptime(x, '%Y-%m-%d').date())
    
    query = Session.query
    
    if student_id:
        query = query.filter_by(student_id=student_id)
    if start_date:
        query = query.filter(Session.session_date >= start_date)
    if end_date:
        query = query.filter(Session.session_date <= end_date)
    
    sessions = query.all()
    return jsonify([s.to_dict() for s in sessions])

@sessions_bp.route('/', methods=['POST'])
@require_auth
def create_session():
    """Create a new session."""
    schema = SessionSchema()
    try:
        data = schema.load(request.json)
        session = Session(**data)
        db.session.add(session)
        db.session.commit()
        return jsonify(session.to_dict()), 201
    except ValidationError as e:
        return jsonify({'error': 'Validation failed', 'messages': e.messages}), 400

@sessions_bp.route('/<int:session_id>', methods=['PUT'])
@require_auth
def update_session(session_id):
    """Update a session."""
    session = Session.query.get_or_404(session_id)
    data = request.json
    
    for key, value in data.items():
        if hasattr(session, key):
            setattr(session, key, value)
    
    db.session.commit()
    return jsonify(session.to_dict())
