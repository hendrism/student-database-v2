from flask import Blueprint, request, jsonify, current_app
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from marshmallow import Schema, fields, ValidationError, validate
from sqlalchemy import and_, or_
from models import db, Session, Student
from auth.decorators import require_auth, require_permission
from datetime import datetime, date, time
from zoneinfo import ZoneInfo

# Blueprint and rate limiter setup
sessions_bp = Blueprint('sessions', __name__, url_prefix='/api/v1/sessions')
limiter = Limiter(key_func=get_remote_address)


@sessions_bp.record_once
def on_load(state):
    """Initialize limiter with the application context."""
    limiter.init_app(state.app)


# Validation schema
class SessionSchema(Schema):
    student_id = fields.Int(required=True)
    session_date = fields.Date(required=True)
    start_time = fields.Time(required=True)
    end_time = fields.Time(required=True)
    session_type = fields.Str(validate=validate.OneOf([
        'Individual', 'Group', 'Assessment', 'Consultation'
    ]), missing='Individual')
    status = fields.Str(validate=validate.OneOf([
        'Scheduled', 'Completed', 'Cancelled', 'No Show',
        'Makeup Needed', 'Excused Absence'
    ]), missing='Scheduled')
    location = fields.Str(validate=validate.Length(max=100), allow_none=True)
    notes = fields.Str(validate=validate.Length(max=1000), allow_none=True)


def get_timezone():
    tz_name = (request.json or {}).get('timezone') if request.method in ['POST', 'PUT'] else request.args.get('timezone')
    try:
        return ZoneInfo(tz_name) if tz_name else ZoneInfo('UTC')
    except Exception:
        return ZoneInfo('UTC')


def to_utc(dt: datetime, tz: ZoneInfo) -> datetime:
    """Convert aware datetime in tz to UTC."""
    return dt.replace(tzinfo=tz).astimezone(ZoneInfo('UTC'))


def serialize_session(session: Session, tz: ZoneInfo):
    """Serialize session with timezone adjusted fields."""
    start_dt = datetime.combine(session.session_date, session.start_time, tzinfo=ZoneInfo('UTC')).astimezone(tz)
    end_dt = datetime.combine(session.session_date, session.end_time, tzinfo=ZoneInfo('UTC')).astimezone(tz)
    data = session.to_dict()
    data.update({
        'session_date': start_dt.date().isoformat(),
        'start_time': start_dt.time().strftime('%H:%M'),
        'end_time': end_dt.time().strftime('%H:%M'),
        'duration_minutes': int((end_dt - start_dt).total_seconds() / 60),
        'student': session.student.to_dict(include_sensitive=False)
    })
    return data


def has_conflict(student_id: int, session_date: date, start_time: time, end_time: time, session_id: int | None = None) -> bool:
    """Check for scheduling conflicts for a student."""
    conflict = Session.query.filter(
        Session.student_id == student_id,
        Session.session_date == session_date,
        Session.id != session_id,
        or_(
            and_(Session.start_time < end_time, Session.end_time > start_time)
        )
    ).first()
    return conflict is not None


@sessions_bp.errorhandler(ValidationError)
def handle_validation_error(error):
    return jsonify({'error': 'Validation failed', 'messages': error.messages}), 400


@sessions_bp.route('/', methods=['GET'])
@require_auth
@limiter.limit('20 per minute')
def list_sessions():
    """List sessions with filtering and pagination."""
    try:
        tz = get_timezone()
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        query = Session.query.join(Student)

        student_id = request.args.get('student_id', type=int)
        if student_id:
            query = query.filter(Session.student_id == student_id)
        start_date = request.args.get('start_date')
        if start_date:
            d = datetime.strptime(start_date, '%Y-%m-%d').date()
            d_utc = to_utc(datetime.combine(d, time.min), tz).date()
            query = query.filter(Session.session_date >= d_utc)
        end_date = request.args.get('end_date')
        if end_date:
            d = datetime.strptime(end_date, '%Y-%m-%d').date()
            d_utc = to_utc(datetime.combine(d, time.max), tz).date()
            query = query.filter(Session.session_date <= d_utc)
        status = request.args.get('status')
        if status:
            query = query.filter(Session.status == status)
        session_type = request.args.get('session_type')
        if session_type:
            query = query.filter(Session.session_type == session_type)

        pagination = query.order_by(Session.session_date.desc(), Session.start_time.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        sessions = [serialize_session(s, tz) for s in pagination.items]
        return jsonify({
            'sessions': sessions,
            'pagination': {
                'page': page,
                'pages': pagination.pages,
                'per_page': per_page,
                'total': pagination.total,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            }
        })
    except Exception as e:
        current_app.logger.error(f'Error retrieving sessions: {e}')
        return jsonify({'error': 'Failed to retrieve sessions'}), 500


@sessions_bp.route('/', methods=['POST'])
@require_auth
@require_permission('write')
@limiter.limit('5 per minute')
def create_session():
    """Create a new session."""
    try:
        schema = SessionSchema()
        data = schema.load(request.json)
        tz = get_timezone()

        start_dt_local = datetime.combine(data['session_date'], data['start_time'])
        end_dt_local = datetime.combine(data['session_date'], data['end_time'])
        start_dt = to_utc(start_dt_local, tz)
        end_dt = to_utc(end_dt_local, tz)
        if end_dt <= start_dt:
            return jsonify({'error': 'End time must be after start time'}), 400

        if has_conflict(data['student_id'], start_dt.date(), start_dt.time(), end_dt.time()):
            return jsonify({'error': 'Scheduling conflict for student'}), 409

        session = Session(
            student_id=data['student_id'],
            session_date=start_dt.date(),
            start_time=start_dt.time(),
            end_time=end_dt.time(),
            session_type=data.get('session_type', 'Individual'),
            status=data.get('status', 'Scheduled'),
            location=data.get('location'),
            notes=data.get('notes')
        )
        db.session.add(session)
        db.session.commit()
        return jsonify(serialize_session(session, tz)), 201
    except ValidationError as e:
        raise e
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error creating session: {e}')
        return jsonify({'error': 'Failed to create session'}), 500


@sessions_bp.route('/<int:session_id>', methods=['GET'])
@require_auth
@limiter.limit('30 per minute')
def get_session(session_id):
    try:
        tz = get_timezone()
        session = Session.query.get_or_404(session_id)
        return jsonify(serialize_session(session, tz))
    except Exception as e:
        current_app.logger.error(f'Error retrieving session {session_id}: {e}')
        return jsonify({'error': 'Session not found'}), 404


@sessions_bp.route('/<int:session_id>', methods=['PUT'])
@require_auth
@require_permission('write')
@limiter.limit('10 per minute')
def update_session(session_id):
    try:
        session = Session.query.get_or_404(session_id)
        schema = SessionSchema(partial=True)
        data = schema.load(request.json or {}, partial=True)
        tz = get_timezone()

        if any(k in data for k in ['session_date', 'start_time', 'end_time']):
            new_date = data.get('session_date', session.session_date)
            new_start = data.get('start_time', session.start_time)
            new_end = data.get('end_time', session.end_time)
            start_dt = to_utc(datetime.combine(new_date, new_start), tz)
            end_dt = to_utc(datetime.combine(new_date, new_end), tz)
            if end_dt <= start_dt:
                return jsonify({'error': 'End time must be after start time'}), 400
            if has_conflict(session.student_id, start_dt.date(), start_dt.time(), end_dt.time(), session.id):
                return jsonify({'error': 'Scheduling conflict for student'}), 409
            session.session_date = start_dt.date()
            session.start_time = start_dt.time()
            session.end_time = end_dt.time()

        for field in ['session_type', 'status', 'location', 'notes', 'student_id']:
            if field in data:
                setattr(session, field, data[field])

        db.session.commit()
        return jsonify(serialize_session(session, tz))
    except ValidationError as e:
        raise e
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error updating session {session_id}: {e}')
        return jsonify({'error': 'Failed to update session'}), 500


@sessions_bp.route('/<int:session_id>', methods=['DELETE'])
@require_auth
@require_permission('write')
@limiter.limit('5 per minute')
def delete_session(session_id):
    try:
        session = Session.query.get_or_404(session_id)
        db.session.delete(session)
        db.session.commit()
        return jsonify({'message': 'Session deleted successfully'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error deleting session {session_id}: {e}')
        return jsonify({'error': 'Failed to delete session'}), 500


@sessions_bp.route('/<int:session_id>/complete', methods=['POST'])
@require_auth
@require_permission('write')
@limiter.limit('10 per minute')
def complete_session(session_id):
    """Mark a session as completed."""
    try:
        session = Session.query.get_or_404(session_id)
        data = request.json or {}
        tz = get_timezone()

        if 'end_time' in data:
            end_time_obj = datetime.strptime(data['end_time'], '%H:%M').time()
            end_dt = to_utc(datetime.combine(session.session_date, end_time_obj), tz)
            start_dt = datetime.combine(session.session_date, session.start_time, tzinfo=ZoneInfo('UTC'))
            if end_dt <= start_dt:
                return jsonify({'error': 'End time must be after start time'}), 400
            session.end_time = end_dt.time()

        session.status = 'Completed'
        if 'notes' in data:
            session.notes = data['notes']

        db.session.commit()
        return jsonify(serialize_session(session, tz))
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error completing session {session_id}: {e}')
        return jsonify({'error': 'Failed to complete session'}), 500


@sessions_bp.route('/calendar', methods=['GET'])
@require_auth
@limiter.limit('20 per minute')
def sessions_calendar():
    """Calendar view of sessions."""
    try:
        tz = get_timezone()
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        student_id = request.args.get('student_id', type=int)

        query = Session.query.join(Student)
        if student_id:
            query = query.filter(Session.student_id == student_id)
        if start_date:
            d = datetime.strptime(start_date, '%Y-%m-%d').date()
            d_utc = to_utc(datetime.combine(d, time.min), tz).date()
            query = query.filter(Session.session_date >= d_utc)
        if end_date:
            d = datetime.strptime(end_date, '%Y-%m-%d').date()
            d_utc = to_utc(datetime.combine(d, time.max), tz).date()
            query = query.filter(Session.session_date <= d_utc)

        sessions = query.order_by(Session.session_date, Session.start_time).all()
        events = []
        for s in sessions:
            start_dt = datetime.combine(s.session_date, s.start_time, tzinfo=ZoneInfo('UTC')).astimezone(tz)
            end_dt = datetime.combine(s.session_date, s.end_time, tzinfo=ZoneInfo('UTC')).astimezone(tz)
            events.append({
                'id': s.id,
                'title': f"{s.student.display_name} - {s.session_type}",
                'start': start_dt.isoformat(),
                'end': end_dt.isoformat(),
                'status': s.status,
                'student': {
                    'id': s.student_id,
                    'name': s.student.display_name
                }
            })
        return jsonify({'events': events})
    except Exception as e:
        current_app.logger.error(f'Error retrieving session calendar: {e}')
        return jsonify({'error': 'Failed to retrieve calendar'}), 500
