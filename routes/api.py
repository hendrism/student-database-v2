from flask import jsonify, current_app
from datetime import datetime
from extensions import db
from models import Student, Goal
from sqlalchemy import text

from . import bp_api

@bp_api.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    try:
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

# Simple dashboard analytics
@bp_api.route('/analytics/dashboard', methods=['GET'])
def get_dashboard_analytics():
    """Get dashboard analytics data."""
    try:
        total_students = Student.query.filter(Student.active.is_(True)).count()
        total_goals = Goal.query.filter(Goal.active.is_(True)).count()

        return jsonify({
            'stats': {
                'total_students': total_students,
                'total_goals': total_goals,
                'sessions_this_week': 0,
                'completion_rate': 95
            },
            'recent_activity': []
        })
    except Exception as e:
        current_app.logger.error(f'Error retrieving dashboard analytics: {str(e)}')
        return jsonify({'error': 'Failed to retrieve analytics'}), 500
