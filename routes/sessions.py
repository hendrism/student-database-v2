from flask import Blueprint, request, jsonify
from auth.decorators import token_required, role_required
from models import db, Session, Student, TrialLog, Objective
from utils.validators import validate_session_data, validate_trial_log_data, validate_date_range
from datetime import datetime, date, time
import logging

logger = logging.getLogger(__name__)
sessions_bp = Blueprint('sessions', __name__, url_prefix='/api/sessions')

@sessions_bp.route('/', methods=['GET'])
@token_required
def get_all_sessions():
    """Get all sessions with filtering and pagination."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        
        query = Session.query
        
        # Filter by student
        student_id = request.args.get('student_id', type=int)
        if student_id:
            query = query.filter(Session.student_id == student_id)
        
        # Filter by date range
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        if start_date:
            query = query.filter(Session.session_date >= datetime.strptime(start_date, '%Y-%m-%d').date())
        if end_date:
            query = query.filter(Session.session_date <= datetime.strptime(end_date, '%Y-%m-%d').date())
        
        # Filter by session type
        session_type = request.args.get('session_type')
        if session_type:
            query = query.filter(Session.session_type == session_type)
        
        # Filter by status
        status = request.args.get('status')
        if status:
            query = query.filter(Session.status == status)
        
        sessions = query.order_by(Session.session_date.desc(), Session.start_time.desc()).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        return jsonify({
            'sessions': [session.to_dict() for session in sessions.items],
            'pagination': {
                'page': page,
                'pages': sessions.pages,
                'per_page': per_page,
                'total': sessions.total,
                'has_next': sessions.has_next,
                'has_prev': sessions.has_prev
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error retrieving sessions: {e}")
        return jsonify({'error': 'Failed to retrieve sessions'}), 500

@sessions_bp.route('/<int:session_id>', methods=['GET'])
@token_required
def get_session(session_id):
    """Get a specific session by ID."""
    try:
        session = Session.query.get_or_404(session_id)
        return jsonify(session.to_dict()), 200
        
    except Exception as e:
        logger.error(f"Error retrieving session {session_id}: {e}")
        return jsonify({'error': 'Session not found'}), 404

@sessions_bp.route('/', methods=['POST'])
@token_required
@role_required(['admin', 'teacher'])
def create_session():
    """Create a new session."""
    try:
        data = request.get_json()
        
        # Validate required fields
        validation_error = validate_session_data(data)
        if validation_error:
            return jsonify({'error': validation_error}), 400
        
        # Verify student exists
        student = Student.query.get(data.get('student_id'))
        if not student:
            return jsonify({'error': 'Student not found'}), 404
        
        # Parse times
        start_time = datetime.strptime(data.get('start_time', '09:00'), '%H:%M').time()
        end_time = datetime.strptime(data.get('end_time', '10:00'), '%H:%M').time()
        
        if start_time >= end_time:
            return jsonify({'error': 'End time must be after start time'}), 400
        
        session = Session(
            student_id=data.get('student_id'),
            session_date=datetime.strptime(data.get('session_date'), '%Y-%m-%d').date(),
            start_time=start_time,
            end_time=end_time,
            session_type=data.get('session_type', 'Individual'),
            status=data.get('status', 'Scheduled'),
            location=data.get('location'),
            notes=data.get('notes')
        )
        
        db.session.add(session)
        db.session.commit()
        
        logger.info(f"Created session for student {student.display_name}: {session.session_date}")
        return jsonify(session.to_dict()), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating session: {e}")
        return jsonify({'error': 'Failed to create session'}), 500

@sessions_bp.route('/<int:session_id>', methods=['PUT'])
@token_required
@role_required(['admin', 'teacher'])
def update_session(session_id):
    """Update an existing session."""
    try:
        session = Session.query.get_or_404(session_id)
        data = request.get_json()
        
        # Validate data
        validation_error = validate_session_data(data, is_update=True)
        if validation_error:
            return jsonify({'error': validation_error}), 400
        
        # Update fields
        if 'session_date' in data:
            session.session_date = datetime.strptime(data['session_date'], '%Y-%m-%d').date()
        
        if 'start_time' in data:
            session.start_time = datetime.strptime(data['start_time'], '%H:%M').time()
        
        if 'end_time' in data:
            session.end_time = datetime.strptime(data['end_time'], '%H:%M').time()
        
        # Validate time order
        if session.start_time >= session.end_time:
            return jsonify({'error': 'End time must be after start time'}), 400
        
        # Update other fields
        updatable_fields = ['session_type', 'status', 'location', 'notes']
        for field in updatable_fields:
            if field in data:
                setattr(session, field, data[field])
        
        db.session.commit()
        
        logger.info(f"Updated session {session_id}")
        return jsonify(session.to_dict()), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating session {session_id}: {e}")
        return jsonify({'error': 'Failed to update session'}), 500

@sessions_bp.route('/<int:session_id>', methods=['DELETE'])
@token_required
@role_required(['admin', 'teacher'])
def delete_session(session_id):
    """Delete a session."""
    try:
        session = Session.query.get_or_404(session_id)
        
        db.session.delete(session)
        db.session.commit()
        
        logger.info(f"Deleted session {session_id}")
        return jsonify({'message': 'Session deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting session {session_id}: {e}")
        return jsonify({'error': 'Failed to delete session'}), 500

@sessions_bp.route('/student/<int:student_id>', methods=['GET'])
@token_required
def get_student_sessions(student_id):
    """Get all sessions for a specific student."""
    try:
        student = Student.query.get_or_404(student_id)
        
        # Date filtering
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        query = Session.query.filter(Session.student_id == student_id)
        
        if start_date:
            query = query.filter(Session.session_date >= datetime.strptime(start_date, '%Y-%m-%d').date())
        if end_date:
            query = query.filter(Session.session_date <= datetime.strptime(end_date, '%Y-%m-%d').date())
        
        sessions = query.order_by(Session.session_date.desc()).all()
        
        return jsonify({
            'student_id': student_id,
            'student_name': student.display_name,
            'sessions': [session.to_dict() for session in sessions]
        }), 200
        
    except Exception as e:
        logger.error(f"Error retrieving sessions for student {student_id}: {e}")
        return jsonify({'error': 'Failed to retrieve student sessions'}), 500

@sessions_bp.route('/trial-logs', methods=['GET'])
@token_required
def get_trial_logs():
    """Get trial logs with filtering."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)
        
        query = TrialLog.query
        
        # Filter by student
        student_id = request.args.get('student_id', type=int)
        if student_id:
            query = query.filter(TrialLog.student_id == student_id)
        
        # Filter by objective
        objective_id = request.args.get('objective_id', type=int)
        if objective_id:
            query = query.filter(TrialLog.objective_id == objective_id)
        
        # Date range filtering
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        if start_date:
            query = query.filter(TrialLog.session_date >= datetime.strptime(start_date, '%Y-%m-%d').date())
        if end_date:
            query = query.filter(TrialLog.session_date <= datetime.strptime(end_date, '%Y-%m-%d').date())
        
        trial_logs = query.order_by(TrialLog.session_date.desc()).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        return jsonify({
            'trial_logs': [log.to_dict() for log in trial_logs.items],
            'pagination': {
                'page': page,
                'pages': trial_logs.pages,
                'per_page': per_page,
                'total': trial_logs.total,
                'has_next': trial_logs.has_next,
                'has_prev': trial_logs.has_prev
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error retrieving trial logs: {e}")
        return jsonify({'error': 'Failed to retrieve trial logs'}), 500

@sessions_bp.route('/trial-logs', methods=['POST'])
@token_required
@role_required(['admin', 'teacher'])
def create_trial_log():
    """Create a new trial log entry."""
    try:
        data = request.get_json()
        
        # Validate required fields
        validation_error = validate_trial_log_data(data)
        if validation_error:
            return jsonify({'error': validation_error}), 400
        
        # Verify objective exists
        if data.get('objective_id'):
            objective = Objective.query.get(data.get('objective_id'))
            if not objective:
                return jsonify({'error': 'Objective not found'}), 404
            student_id = objective.goal.student_id
        else:
            student_id = data.get('student_id')
            if not student_id:
                return jsonify({'error': 'Either objective_id or student_id is required'}), 400
        
        # Verify student exists
        student = Student.query.get(student_id)
        if not student:
            return jsonify({'error': 'Student not found'}), 404
        
        trial_log = TrialLog(
            student_id=student_id,
            objective_id=data.get('objective_id'),
            session_date=datetime.strptime(data.get('session_date'), '%Y-%m-%d').date(),
            independent=data.get('independent', 0),
            minimal_support=data.get('minimal_support', 0),
            moderate_support=data.get('moderate_support', 0),
            maximal_support=data.get('maximal_support', 0),
            incorrect=data.get('incorrect', 0),
            session_notes=data.get('session_notes'),
            environmental_factors=data.get('environmental_factors')
        )
        
        db.session.add(trial_log)
        db.session.commit()
        
        logger.info(f"Created trial log for student {student.display_name}")
        return jsonify(trial_log.to_dict()), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating trial log: {e}")
        return jsonify({'error': 'Failed to create trial log'}), 500

@sessions_bp.route('/trial-logs/<int:log_id>', methods=['PUT'])
@token_required
@role_required(['admin', 'teacher'])
def update_trial_log(log_id):
    """Update an existing trial log."""
    try:
        trial_log = TrialLog.query.get_or_404(log_id)
        data = request.get_json()
        
        # Validate data
        validation_error = validate_trial_log_data(data, is_update=True)
        if validation_error:
            return jsonify({'error': validation_error}), 400
        
        # Update fields
        updatable_fields = [
            'session_date', 'independent', 'minimal_support', 'moderate_support',
            'maximal_support', 'incorrect', 'session_notes', 'environmental_factors'
        ]
        
        for field in updatable_fields:
            if field in data:
                if field == 'session_date':
                    setattr(trial_log, field, datetime.strptime(data[field], '%Y-%m-%d').date())
                else:
                    setattr(trial_log, field, data[field])
        
        db.session.commit()
        
        logger.info(f"Updated trial log {log_id}")
        return jsonify(trial_log.to_dict()), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating trial log {log_id}: {e}")
        return jsonify({'error': 'Failed to update trial log'}), 500

@sessions_bp.route('/trial-logs/<int:log_id>', methods=['DELETE'])
@token_required
@role_required(['admin', 'teacher'])
def delete_trial_log(log_id):
    """Delete a trial log entry."""
    try:
        trial_log = TrialLog.query.get_or_404(log_id)
        
        db.session.delete(trial_log)
        db.session.commit()
        
        logger.info(f"Deleted trial log {log_id}")
        return jsonify({'message': 'Trial log deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting trial log {log_id}: {e}")
        return jsonify({'error': 'Failed to delete trial log'}), 500

@sessions_bp.route('/schedule', methods=['GET'])
@token_required
def get_schedule():
    """Get session schedule for a date range."""
    try:
        start_date = request.args.get('start_date', date.today().isoformat())
        end_date = request.args.get('end_date', date.today().isoformat())
        
        # Validate date range
        date_error = validate_date_range(start_date, end_date)
        if date_error:
            return jsonify({'error': date_error}), 400
        
        sessions = Session.query.filter(
            Session.session_date.between(
                datetime.strptime(start_date, '%Y-%m-%d').date(),
                datetime.strptime(end_date, '%Y-%m-%d').date()
            )
        ).order_by(Session.session_date, Session.start_time).all()
        
        # Group by date
        schedule = {}
        for session in sessions:
            date_str = session.session_date.isoformat()
            if date_str not in schedule:
                schedule[date_str] = []
            
            session_data = session.to_dict()
            session_data['student_name'] = session.student.display_name
            schedule[date_str].append(session_data)
        
        return jsonify({
            'start_date': start_date,
            'end_date': end_date,
            'schedule': schedule
        }), 200
        
    except Exception as e:
        logger.error(f"Error retrieving schedule: {e}")
        return jsonify({'error': 'Failed to retrieve schedule'}), 500

@sessions_bp.route('/stats', methods=['GET'])
@token_required
def get_session_stats():
    """Get session statistics."""
    try:
        # Date range for stats
        days_back = request.args.get('days', 30, type=int)
        start_date = date.today().replace(day=1)  # First day of current month
        
        # Basic session counts
        total_sessions = Session.query.count()
        recent_sessions = Session.query.filter(
            Session.session_date >= start_date
        ).count()
        
        # Session type distribution
        session_types = db.session.query(
            Session.session_type,
            db.func.count(Session.id).label('count')
        ).group_by(Session.session_type).all()
        
        # Status distribution
        session_status = db.session.query(
            Session.status,
            db.func.count(Session.id).label('count')
        ).group_by(Session.status).all()
        
        return jsonify({
            'total_sessions': total_sessions,
            'recent_sessions': recent_sessions,
            'session_type_distribution': {st: count for st, count in session_types},
            'status_distribution': {status: count for status, count in session_status},
            'stats_period': f"Current month starting {start_date}"
        }), 200
        
    except Exception as e:
        logger.error(f"Error retrieving session statistics: {e}")
        return jsonify({'error': 'Failed to retrieve statistics'}), 500