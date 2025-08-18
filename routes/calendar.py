# routes/calendar.py - FullCalendar API integration
from flask import Blueprint, request, jsonify, current_app
from marshmallow import Schema, fields, ValidationError, validate
from datetime import datetime, date, time, timedelta
from extensions import db
from models import Session, Student
from auth.decorators import require_auth, require_permission

calendar_bp = Blueprint('calendar', __name__)

# Validation Schemas
class EventCreateSchema(Schema):
    student_id = fields.Int(required=True)
    session_date = fields.Date(required=True)
    start_time = fields.Time(required=True)
    end_time = fields.Time(required=True)
    event_type = fields.Str(validate=validate.OneOf([
        'Session', 'Meeting', 'Assessment', 'Reminder', 'Other'
    ]), load_default='Session')
    session_type = fields.Str(validate=validate.OneOf([
        'Individual', 'Group', 'Assessment', 'Consultation'
    ]), load_default='Individual')
    location = fields.Str(validate=validate.Length(max=100), allow_none=True)
    notes = fields.Str(validate=validate.Length(max=1000), allow_none=True)
    plan_notes = fields.Str(validate=validate.Length(max=1000), allow_none=True)

class EventUpdateSchema(Schema):
    session_date = fields.Date(allow_none=True)
    start_time = fields.Time(allow_none=True)
    end_time = fields.Time(allow_none=True)
    status = fields.Str(validate=validate.OneOf([
        'Scheduled', 'Completed', 'Cancelled', 'No Show', 'Makeup Needed', 'Excused Absence'
    ]), allow_none=True)
    location = fields.Str(validate=validate.Length(max=100), allow_none=True)
    notes = fields.Str(validate=validate.Length(max=1000), allow_none=True)
    plan_notes = fields.Str(validate=validate.Length(max=1000), allow_none=True)

@calendar_bp.route('/api/calendar/events', methods=['GET'])
@require_auth
def get_calendar_events():
    """Get events for FullCalendar with date range filtering."""
    
    try:
        # Get date range from FullCalendar
        start_str = request.args.get('start')
        end_str = request.args.get('end')
        student_id = request.args.get('student_id', type=int)
        event_type = request.args.get('event_type')
        
        # Parse dates
        if start_str and end_str:
            start_date = datetime.fromisoformat(start_str.replace('Z', '+00:00')).date()
            end_date = datetime.fromisoformat(end_str.replace('Z', '+00:00')).date()
        else:
            # Default to current month
            today = date.today()
            start_date = today.replace(day=1)
            end_date = (start_date + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        # Build query
        query = Session.query.filter(
            Session.session_date >= start_date,
            Session.session_date <= end_date
        )
        
        if student_id:
            query = query.filter(Session.student_id == student_id)
            
        if event_type:
            query = query.filter(Session.event_type == event_type)
        
        sessions = query.order_by(Session.session_date, Session.start_time).all()
        
        # Convert to FullCalendar format
        events = [session.to_calendar_event() for session in sessions]
        
        current_app.logger.info(f'Retrieved {len(events)} calendar events')
        
        return jsonify(events)
        
    except Exception as e:
        current_app.logger.error(f'Error retrieving calendar events: {str(e)}')
        return jsonify({'error': 'Failed to retrieve calendar events'}), 500

@calendar_bp.route('/api/calendar/events', methods=['POST'])
@require_auth
@require_permission('write')
def create_calendar_event():
    """Create a new calendar event/session."""
    
    try:
        schema = EventCreateSchema()
        event_data = schema.load(request.json)
        
        # Validate student exists
        student = Student.query.get_or_404(event_data['student_id'])
        
        # Validate time logic
        if event_data['start_time'] >= event_data['end_time']:
            return jsonify({'error': 'End time must be after start time'}), 400
        
        # Check for conflicts
        conflicts = Session.query.filter(
            Session.student_id == event_data['student_id'],
            Session.session_date == event_data['session_date'],
            Session.start_time < event_data['end_time'],
            Session.end_time > event_data['start_time'],
            Session.status.in_(['Scheduled', 'Completed'])
        ).first()
        
        if conflicts:
            return jsonify({
                'error': 'Time conflict detected',
                'conflicting_session': conflicts.to_dict()
            }), 409
        
        # Create session
        session = Session(**event_data)
        db.session.add(session)
        db.session.commit()
        
        current_app.logger.info(f'Created calendar event for {student.display_name}')
        
        return jsonify({
            'message': 'Event created successfully',
            'event': session.to_calendar_event()
        }), 201
        
    except ValidationError as e:
        return jsonify({'error': 'Validation failed', 'messages': e.messages}), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error creating calendar event: {str(e)}')
        return jsonify({'error': 'Failed to create event'}), 500

@calendar_bp.route('/api/calendar/events/<int:event_id>', methods=['PUT'])
@require_auth
@require_permission('write')
def update_calendar_event(event_id):
    """Update a calendar event/session."""
    
    try:
        session = Session.query.get_or_404(event_id)
        
        schema = EventUpdateSchema()
        update_data = schema.load(request.json)
        
        # Validate time logic if both times provided
        if ('start_time' in update_data and 'end_time' in update_data and 
            update_data['start_time'] and update_data['end_time']):
            if update_data['start_time'] >= update_data['end_time']:
                return jsonify({'error': 'End time must be after start time'}), 400
        
        # Update session
        for key, value in update_data.items():
            if value is not None:
                setattr(session, key, value)
        
        db.session.commit()
        
        current_app.logger.info(f'Updated calendar event {event_id}')
        
        return jsonify({
            'message': 'Event updated successfully',
            'event': session.to_calendar_event()
        })
        
    except ValidationError as e:
        return jsonify({'error': 'Validation failed', 'messages': e.messages}), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error updating calendar event {event_id}: {str(e)}')
        return jsonify({'error': 'Failed to update event'}), 500

@calendar_bp.route('/api/calendar/events/<int:event_id>', methods=['DELETE'])
@require_auth
@require_permission('write')
def delete_calendar_event(event_id):
    """Delete a calendar event/session."""
    
    try:
        session = Session.query.get_or_404(event_id)
        
        # Check if session has trial logs
        if session.trial_logs:
            return jsonify({
                'error': 'Cannot delete session with trial log data. Archive instead.'
            }), 400
        
        db.session.delete(session)
        db.session.commit()
        
        current_app.logger.info(f'Deleted calendar event {event_id}')
        
        return jsonify({'message': 'Event deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error deleting calendar event {event_id}: {str(e)}')
        return jsonify({'error': 'Failed to delete event'}), 500

@calendar_bp.route('/api/calendar/events/<int:event_id>/create-makeup', methods=['POST'])
@require_auth
@require_permission('write')
def create_makeup_session(event_id):
    """Create a makeup session for a missed session."""
    
    try:
        original_session = Session.query.get_or_404(event_id)
        
        # Validate original session can have makeup
        if original_session.status not in ['Makeup Needed', 'No Show']:
            return jsonify({
                'error': 'Only sessions marked as "Makeup Needed" or "No Show" can have makeups'
            }), 400
        
        # Get makeup session details
        makeup_data = request.json
        
        schema = EventCreateSchema()
        makeup_details = schema.load({
            'student_id': original_session.student_id,
            'session_date': makeup_data['session_date'],
            'start_time': makeup_data['start_time'],
            'end_time': makeup_data['end_time'],
            'event_type': original_session.event_type,
            'session_type': original_session.session_type,
            'location': makeup_data.get('location', original_session.location)
        })
        
        # Create makeup session
        makeup_session = original_session.create_makeup_session(
            makeup_details['session_date'],
            makeup_details['start_time'],
            makeup_details['end_time']
        )
        
        if 'location' in makeup_data:
            makeup_session.location = makeup_data['location']
        
        db.session.commit()
        
        current_app.logger.info(f'Created makeup session for event {event_id}')
        
        return jsonify({
            'message': 'Makeup session created successfully',
            'makeup_session': makeup_session.to_calendar_event()
        }), 201
        
    except ValidationError as e:
        return jsonify({'error': 'Validation failed', 'messages': e.messages}), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error creating makeup session: {str(e)}')
        return jsonify({'error': 'Failed to create makeup session'}), 500

@calendar_bp.route('/api/calendar/bulk-sessions', methods=['POST'])
@require_auth
@require_permission('write')
def create_bulk_sessions():
    """Create multiple sessions for all active students."""
    
    try:
        bulk_data = request.json
        session_date = datetime.strptime(bulk_data['session_date'], '%Y-%m-%d').date()
        default_duration = bulk_data.get('duration_minutes', 30)
        
        students = Student.query.filter(Student.active == True).all()
        created_sessions = []
        
        for student in students:
            # Skip if student already has session on this date
            existing = Session.query.filter(
                Session.student_id == student.id,
                Session.session_date == session_date
            ).first()
            
            if existing:
                continue
            
            # Calculate time slot (simple scheduling)
            start_time = time(9, 0)  # Start at 9 AM
            session_count = len(created_sessions)
            start_minutes = 9 * 60 + (session_count * default_duration)
            
            start_hour = start_minutes // 60
            start_minute = start_minutes % 60
            end_minutes = start_minutes + default_duration
            end_hour = end_minutes // 60
            end_minute = end_minutes % 60
            
            if start_hour >= 17:  # Don't schedule past 5 PM
                break
            
            session = Session(
                student_id=student.id,
                session_date=session_date,
                start_time=time(start_hour, start_minute),
                end_time=time(end_hour, end_minute),
                event_type='Session',
                session_type='Individual',
                status='Scheduled'
            )
            
            db.session.add(session)
            created_sessions.append(session)
        
        db.session.commit()
        
        current_app.logger.info(f'Created {len(created_sessions)} bulk sessions')
        
        return jsonify({
            'message': f'Created {len(created_sessions)} sessions',
            'sessions': [session.to_calendar_event() for session in created_sessions]
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error creating bulk sessions: {str(e)}')
        return jsonify({'error': 'Failed to create bulk sessions'}), 500

@calendar_bp.route('/api/calendar/conflicts', methods=['GET'])
@require_auth
def check_scheduling_conflicts():
    """Check for scheduling conflicts on a given date."""
    
    try:
        check_date = datetime.strptime(request.args.get('date'), '%Y-%m-%d').date()
        
        # Find overlapping sessions
        sessions = Session.query.filter(
            Session.session_date == check_date,
            Session.status.in_(['Scheduled', 'Completed'])
        ).order_by(Session.start_time).all()
        
        conflicts = []
        
        for i, session1 in enumerate(sessions):
            for session2 in sessions[i+1:]:
                # Check for time overlap
                if (session1.start_time < session2.end_time and 
                    session1.end_time > session2.start_time):
                    
                    conflicts.append({
                        'session1': session1.to_dict(),
                        'session2': session2.to_dict(),
                        'type': 'time_overlap'
                    })
        
        return jsonify({
            'date': check_date.isoformat(),
            'conflicts': conflicts,
            'total_sessions': len(sessions)
        })
        
    except Exception as e:
        current_app.logger.error(f'Error checking conflicts: {str(e)}')
        return jsonify({'error': 'Failed to check conflicts'}), 500