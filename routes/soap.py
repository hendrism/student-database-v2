from flask import Blueprint, request, jsonify
from marshmallow import Schema, ValidationError, fields, validate
from extensions import db
from models import SOAPNote, Student
from auth.decorators import require_auth
from datetime import date

soap_bp = Blueprint('soap', __name__, url_prefix='/api/soap')

class SOAPNoteSchema(Schema):
    student_id = fields.Int(required=True)
    session_date = fields.Date(required=True)
    subjective = fields.Str(validate=validate.Length(max=2000))
    objective = fields.Str(validate=validate.Length(max=2000))
    assessment = fields.Str(validate=validate.Length(max=2000))
    plan = fields.Str(validate=validate.Length(max=2000))
    clinician_signature = fields.Str(validate=validate.Length(max=100))

@soap_bp.route('/', methods=['GET'])
@require_auth
def get_soap_notes():
    """Get SOAP notes with optional filtering."""
    student_id = request.args.get('student_id', type=int)
    
    query = SOAPNote.query
    if student_id:
        query = query.filter_by(student_id=student_id)
    
    notes = query.all()
    return jsonify([n.to_dict() for n in notes])

@soap_bp.route('/', methods=['POST'])
@require_auth
def create_soap_note():
    """Create a new SOAP note."""
    schema = SOAPNoteSchema()
    try:
        data = schema.load(request.json)
        note = SOAPNote(**data)
        db.session.add(note)
        db.session.commit()
        return jsonify(note.to_dict()), 201
    except ValidationError as e:
        return jsonify({'error': 'Validation failed', 'messages': e.messages}), 400

@soap_bp.route('/<int:note_id>', methods=['GET'])
@require_auth
def get_soap_note(note_id):
    """Get a specific SOAP note."""
    note = SOAPNote.query.get_or_404(note_id)
    return jsonify(note.to_dict())

@soap_bp.route('/<int:note_id>', methods=['PUT'])
@require_auth
def update_soap_note(note_id):
    """Update a SOAP note."""
    note = SOAPNote.query.get_or_404(note_id)
    data = request.json
    
    for key, value in data.items():
        if hasattr(note, key):
            setattr(note, key, value)
    
    db.session.commit()
    return jsonify(note.to_dict())
