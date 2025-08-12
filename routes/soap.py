from flask import Blueprint, request, jsonify
from auth.decorators import token_required, role_required
from models import db, SOAPNote, Student, Session
from utils.validators import validate_soap_data
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)
soap_bp = Blueprint('soap', __name__, url_prefix='/api/soap')

@soap_bp.route('/', methods=['GET'])
@token_required
def get_all_soap_notes():
    """Get all SOAP notes with filtering and pagination."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        include_content = request.args.get('include_content', 'true').lower() == 'true'
        
        query = SOAPNote.query
        
        # Filter by student
        student_id = request.args.get('student_id', type=int)
        if student_id:
            query = query.filter(SOAPNote.student_id == student_id)
        
        # Filter by date range
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        if start_date:
            query = query.filter(SOAPNote.session_date >= datetime.strptime(start_date, '%Y-%m-%d').date())
        if end_date:
            query = query.filter(SOAPNote.session_date <= datetime.strptime(end_date, '%Y-%m-%d').date())
        
        # Filter by anonymization status
        anonymized = request.args.get('anonymized')
        if anonymized is not None:
            is_anonymized = anonymized.lower() == 'true'
            query = query.filter(SOAPNote.anonymized == is_anonymized)
        
        soap_notes = query.order_by(SOAPNote.session_date.desc()).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        return jsonify({
            'soap_notes': [note.to_dict(include_content=include_content) for note in soap_notes.items],
            'pagination': {
                'page': page,
                'pages': soap_notes.pages,
                'per_page': per_page,
                'total': soap_notes.total,
                'has_next': soap_notes.has_next,
                'has_prev': soap_notes.has_prev
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error retrieving SOAP notes: {e}")
        return jsonify({'error': 'Failed to retrieve SOAP notes'}), 500

@soap_bp.route('/<int:note_id>', methods=['GET'])
@token_required
def get_soap_note(note_id):
    """Get a specific SOAP note by ID."""
    try:
        include_content = request.args.get('include_content', 'true').lower() == 'true'
        
        soap_note = SOAPNote.query.get_or_404(note_id)
        return jsonify(soap_note.to_dict(include_content=include_content)), 200
        
    except Exception as e:
        logger.error(f"Error retrieving SOAP note {note_id}: {e}")
        return jsonify({'error': 'SOAP note not found'}), 404

@soap_bp.route('/', methods=['POST'])
@token_required
@role_required(['admin', 'teacher'])
def create_soap_note():
    """Create a new SOAP note."""
    try:
        data = request.get_json()
        
        # Validate required fields
        validation_error = validate_soap_data(data)
        if validation_error:
            return jsonify({'error': validation_error}), 400
        
        # Verify student exists
        student = Student.query.get(data.get('student_id'))
        if not student:
            return jsonify({'error': 'Student not found'}), 404
        
        # Verify session exists if provided
        session_id = data.get('session_id')
        if session_id:
            session = Session.query.get(session_id)
            if not session:
                return jsonify({'error': 'Session not found'}), 404
            if session.student_id != data.get('student_id'):
                return jsonify({'error': 'Session does not belong to the specified student'}), 400
        
        soap_note = SOAPNote(
            student_id=data.get('student_id'),
            session_id=session_id,
            session_date=datetime.strptime(data.get('session_date'), '%Y-%m-%d').date(),
            subjective=data.get('subjective'),
            objective=data.get('objective'),
            assessment=data.get('assessment'),
            plan=data.get('plan'),
            clinician_signature=data.get('clinician_signature')
        )
        
        db.session.add(soap_note)
        db.session.commit()
        
        logger.info(f"Created SOAP note for student {student.display_name} on {soap_note.session_date}")
        return jsonify(soap_note.to_dict()), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating SOAP note: {e}")
        return jsonify({'error': 'Failed to create SOAP note'}), 500

@soap_bp.route('/<int:note_id>', methods=['PUT'])
@token_required
@role_required(['admin', 'teacher'])
def update_soap_note(note_id):
    """Update an existing SOAP note."""
    try:
        soap_note = SOAPNote.query.get_or_404(note_id)
        data = request.get_json()
        
        # Don't allow editing anonymized notes
        if soap_note.anonymized:
            return jsonify({'error': 'Cannot edit anonymized SOAP note'}), 400
        
        # Validate data
        validation_error = validate_soap_data(data, is_update=True)
        if validation_error:
            return jsonify({'error': validation_error}), 400
        
        # Update session date if provided
        if 'session_date' in data:
            soap_note.session_date = datetime.strptime(data['session_date'], '%Y-%m-%d').date()
        
        # Update SOAP sections
        soap_sections = ['subjective', 'objective', 'assessment', 'plan']
        for section in soap_sections:
            if section in data:
                setattr(soap_note, section, data[section])
        
        # Update other fields
        if 'clinician_signature' in data:
            soap_note.clinician_signature = data['clinician_signature']
        
        # Update session_id if provided
        if 'session_id' in data:
            session_id = data['session_id']
            if session_id:
                session = Session.query.get(session_id)
                if not session:
                    return jsonify({'error': 'Session not found'}), 404
                if session.student_id != soap_note.student_id:
                    return jsonify({'error': 'Session does not belong to this student'}), 400
            soap_note.session_id = session_id
        
        db.session.commit()
        
        logger.info(f"Updated SOAP note {note_id}")
        return jsonify(soap_note.to_dict()), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating SOAP note {note_id}: {e}")
        return jsonify({'error': 'Failed to update SOAP note'}), 500

@soap_bp.route('/<int:note_id>', methods=['DELETE'])
@token_required
@role_required(['admin'])
def delete_soap_note(note_id):
    """Delete a SOAP note (admin only)."""
    try:
        soap_note = SOAPNote.query.get_or_404(note_id)
        
        db.session.delete(soap_note)
        db.session.commit()
        
        logger.info(f"Deleted SOAP note {note_id}")
        return jsonify({'message': 'SOAP note deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting SOAP note {note_id}: {e}")
        return jsonify({'error': 'Failed to delete SOAP note'}), 500

@soap_bp.route('/student/<int:student_id>', methods=['GET'])
@token_required
def get_student_soap_notes(student_id):
    """Get all SOAP notes for a specific student."""
    try:
        student = Student.query.get_or_404(student_id)
        include_content = request.args.get('include_content', 'true').lower() == 'true'
        
        # Date filtering
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        query = SOAPNote.query.filter(SOAPNote.student_id == student_id)
        
        if start_date:
            query = query.filter(SOAPNote.session_date >= datetime.strptime(start_date, '%Y-%m-%d').date())
        if end_date:
            query = query.filter(SOAPNote.session_date <= datetime.strptime(end_date, '%Y-%m-%d').date())
        
        soap_notes = query.order_by(SOAPNote.session_date.desc()).all()
        
        return jsonify({
            'student_id': student_id,
            'student_name': student.display_name,
            'soap_notes': [note.to_dict(include_content=include_content) for note in soap_notes]
        }), 200
        
    except Exception as e:
        logger.error(f"Error retrieving SOAP notes for student {student_id}: {e}")
        return jsonify({'error': 'Failed to retrieve student SOAP notes'}), 500

@soap_bp.route('/<int:note_id>/anonymize', methods=['POST'])
@token_required
@role_required(['admin'])
def anonymize_soap_note(note_id):
    """Anonymize a SOAP note for privacy compliance."""
    try:
        soap_note = SOAPNote.query.get_or_404(note_id)
        
        if soap_note.anonymized:
            return jsonify({'message': 'SOAP note is already anonymized'}), 200
        
        soap_note.anonymize()
        db.session.commit()
        
        logger.info(f"Anonymized SOAP note {note_id}")
        return jsonify({
            'message': 'SOAP note anonymized successfully',
            'soap_note': soap_note.to_dict(include_content=False)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error anonymizing SOAP note {note_id}: {e}")
        return jsonify({'error': 'Failed to anonymize SOAP note'}), 500

@soap_bp.route('/templates', methods=['GET'])
@token_required
def get_soap_templates():
    """Get SOAP note templates to help with consistent documentation."""
    try:
        templates = {
            'speech_language': {
                'name': 'Speech-Language Pathology',
                'template': {
                    'subjective': 'Client/caregiver reports: [mood, behavior, concerns, home practice]',
                    'objective': 'Therapeutic activities: [specific tasks, materials used, cueing levels]\nPerformance data: [accuracy percentages, trials, support levels]\nBehavioral observations: [attention, cooperation, strategies used]',
                    'assessment': 'Progress toward goals: [specific goal progress]\nStrengths: [areas of success]\nChallenges: [areas needing support]\nRecommendations: [modifications, strategies]',
                    'plan': 'Continue: [successful interventions]\nModify: [adjustments needed]\nNext session: [upcoming focus areas]\nHome practice: [recommendations for caregivers]'
                }
            },
            'occupational_therapy': {
                'name': 'Occupational Therapy',
                'template': {
                    'subjective': 'Client/caregiver reports: [functional concerns, daily activities, participation]',
                    'objective': 'Activities completed: [therapeutic tasks, adaptive equipment used]\nPerformance observations: [motor skills, sensory processing, task completion]\nAssistance levels: [independence, cueing, physical support]',
                    'assessment': 'Functional progress: [ADL skills, academic tasks, play/leisure]\nStrengths: [successful strategies, emerging skills]\nBarriers: [environmental, physical, cognitive factors]\nSafety considerations: [risk factors, precautions]',
                    'plan': 'Treatment focus: [priority areas for intervention]\nStrategies: [therapeutic approaches, accommodations]\nEquipment/modifications: [environmental changes, tools]\nCaregiver education: [home strategies, follow-up]'
                }
            },
            'physical_therapy': {
                'name': 'Physical Therapy',
                'template': {
                    'subjective': 'Client/caregiver reports: [pain levels, functional mobility, activity tolerance]',
                    'objective': 'Therapeutic exercises: [specific activities, repetitions, resistance]\nMobility assessment: [transfers, ambulation, assistive devices]\nRange of motion: [measurements, limitations]\nStrength: [manual muscle testing results]',
                    'assessment': 'Functional mobility progress: [improvements, limitations]\nPain management: [levels, triggers, relief strategies]\nSafety awareness: [fall risk, precautions]\nGoal progress: [objective measurements, functional outcomes]',
                    'plan': 'Exercise progression: [modifications, advancement]\nMobility training: [skills to practice, safety education]\nEquipment needs: [assistive devices, modifications]\nDischarge planning: [timeline, transition preparation]'
                }
            },
            'general': {
                'name': 'General Template',
                'template': {
                    'subjective': 'Client/caregiver reports and observations',
                    'objective': 'Measurable observations, data, and performance during session',
                    'assessment': 'Professional analysis of progress, strengths, and areas for improvement',
                    'plan': 'Treatment modifications, goals, and recommendations moving forward'
                }
            }
        }
        
        return jsonify({'templates': templates}), 200
        
    except Exception as e:
        logger.error(f"Error retrieving SOAP templates: {e}")
        return jsonify({'error': 'Failed to retrieve templates'}), 500

@soap_bp.route('/stats', methods=['GET'])
@token_required
def get_soap_stats():
    """Get SOAP note statistics."""
    try:
        # Basic counts
        total_notes = SOAPNote.query.count()
        anonymized_notes = SOAPNote.query.filter(SOAPNote.anonymized == True).count()
        
        # Recent activity (last 30 days)
        thirty_days_ago = date.today().replace(day=max(1, date.today().day - 30))
        recent_notes = SOAPNote.query.filter(
            SOAPNote.session_date >= thirty_days_ago
        ).count()
        
        # Notes by student
        notes_per_student = db.session.query(
            Student.display_name,
            db.func.count(SOAPNote.id).label('note_count')
        ).join(SOAPNote).group_by(Student.id, Student.display_name).order_by(
            db.func.count(SOAPNote.id).desc()
        ).limit(10).all()
        
        # Monthly distribution
        monthly_counts = db.session.query(
            db.extract('year', SOAPNote.session_date).label('year'),
            db.extract('month', SOAPNote.session_date).label('month'),
            db.func.count(SOAPNote.id).label('count')
        ).group_by(
            db.extract('year', SOAPNote.session_date),
            db.extract('month', SOAPNote.session_date)
        ).order_by('year', 'month').all()
        
        return jsonify({
            'total_notes': total_notes,
            'anonymized_notes': anonymized_notes,
            'recent_notes': recent_notes,
            'completion_rate': f"{((total_notes - anonymized_notes) / total_notes * 100):.1f}%" if total_notes > 0 else "0%",
            'top_students': [
                {'student': name, 'note_count': count} 
                for name, count in notes_per_student
            ],
            'monthly_distribution': [
                {'year': int(year), 'month': int(month), 'count': count}
                for year, month, count in monthly_counts
            ]
        }), 200
        
    except Exception as e:
        logger.error(f"Error retrieving SOAP statistics: {e}")
        return jsonify({'error': 'Failed to retrieve statistics'}), 500