# utils/quarterly_reports.py - Comprehensive quarterly report generation
from datetime import datetime, date, timedelta
import calendar

from extensions import db
from models import Goal, Objective, QuarterlyReport, Session, Student, TrialLog

class QuarterlyReportGenerator:
    """Generate comprehensive quarterly progress reports."""
    
    def __init__(self):
        self.quarters = {
            'Q1': {'months': [1, 2, 3], 'name': 'First Quarter'},
            'Q2': {'months': [4, 5, 6], 'name': 'Second Quarter'}, 
            'Q3': {'months': [7, 8, 9], 'name': 'Third Quarter'},
            'Q4': {'months': [10, 11, 12], 'name': 'Fourth Quarter'}
        }
        
        self.progress_descriptors = {
            90: "excellent progress",
            80: "good progress", 
            70: "satisfactory progress",
            60: "emerging progress",
            50: "limited progress",
            0: "minimal progress"
        }
        
        self.cue_hierarchy = [
            'independent',
            'minimal_support', 
            'moderate_support',
            'maximal_support'
        ]

    def generate_report(self, student_id, quarter, year, goals_data=None):
        """Generate comprehensive quarterly report."""
        
        student = Student.query.get_or_404(student_id)
        
        # Get date range for quarter
        start_date, end_date = self._get_quarter_dates(quarter, year)
        
        # Get trial data for the quarter
        trial_logs = TrialLog.query.filter(
            TrialLog.student_id == student_id,
            TrialLog.session_date >= start_date,
            TrialLog.session_date <= end_date
        ).order_by(TrialLog.session_date).all()
        
        # Get session data
        sessions = Session.query.filter(
            Session.student_id == student_id,
            Session.session_date >= start_date,
            Session.session_date <= end_date,
            Session.status == 'Completed'
        ).all()
        
        # Generate report sections
        report_sections = {
            'header': self._generate_header(student, quarter, year, start_date, end_date),
            'attendance': self._generate_attendance_section(student, sessions, start_date, end_date),
            'goals': self._generate_goals_section(student, trial_logs, goals_data or {}),
            'summary': self._generate_summary_section(student, trial_logs, sessions),
            'recommendations': self._generate_recommendations(student, trial_logs, goals_data or {})
        }
        
        # Compile full report
        full_report = self._compile_report(report_sections)
        
        # Save report to database
        quarterly_report = QuarterlyReport(
            student_id=student_id,
            quarter=f"{quarter} {year}",
            report_text=full_report,
            generated_by=getattr(g, 'current_user', {}).get('username', 'System')
        )
        
        db.session.add(quarterly_report)
        db.session.commit()
        
        return {
            'report_text': full_report,
            'report_id': quarterly_report.id,
            'sections': report_sections,
            'metadata': {
                'student_name': student.display_name,
                'quarter': quarter,
                'year': year,
                'generated_at': datetime.now().isoformat(),
                'total_sessions': len(sessions),
                'total_trial_logs': len(trial_logs)
            }
        }

    def _generate_header(self, student, quarter, year, start_date, end_date):
        """Generate report header section."""
        
        quarter_name = self.quarters[quarter]['name']
        
        header = f"""
QUARTERLY PROGRESS REPORT

Student: {student.first_name} {student.last_name}
Grade: {student.grade_level or 'Not specified'}
Reporting Period: {quarter_name} {year} ({start_date.strftime('%m/%d/%Y')} - {end_date.strftime('%m/%d/%Y')})
Report Generated: {datetime.now().strftime('%m/%d/%Y')}
Monthly Service Frequency: {student.monthly_services or 'Not specified'} sessions per month

""".strip()
        
        return header

    def _generate_attendance_section(self, student, sessions, start_date, end_date):
        """Generate attendance and service delivery section."""
        
        # Calculate expected sessions
        months_in_quarter = 3
        expected_sessions = (student.monthly_services or 4) * months_in_quarter
        completed_sessions = len(sessions)
        
        # Calculate monthly breakdown
        monthly_breakdown = {}
        for month_num in self.quarters[self._get_quarter_from_date(start_date)]['months']:
            month_sessions = [s for s in sessions if s.session_date.month == month_num]
            month_name = calendar.month_name[month_num]
            monthly_breakdown[month_name] = len(month_sessions)
        
        # Calculate attendance rate
        attendance_rate = (completed_sessions / expected_sessions * 100) if expected_sessions > 0 else 0
        
        attendance_section = f"""
SERVICE DELIVERY AND ATTENDANCE

Expected Sessions: {expected_sessions}
Completed Sessions: {completed_sessions}
Attendance Rate: {attendance_rate:.1f}%

Monthly Breakdown:"""
        
        for month, count in monthly_breakdown.items():
            attendance_section += f"\n  • {month}: {count} sessions"
        
        if attendance_rate < 85:
            attendance_section += f"\n\nNote: Attendance rate is below target (85%). Consider makeup sessions or schedule adjustments."
        
        return attendance_section

    def _generate_goals_section(self, student, trial_logs, goals_data):
        """Generate detailed goals and objectives section."""
        
        goals_section = "\nGOALS AND OBJECTIVES PROGRESS\n"
        
        for goal in student.goals:
            if not goal.active:
                continue
                
            goal_section = f"\nGoal: {goal.description}\n"
            goal_section += "=" * 50 + "\n"
            
            # Process objectives under this goal
            for objective in goal.objectives:
                if not objective.active:
                    continue
                    
                # Get trial logs for this objective
                objective_logs = [log for log in trial_logs 
                                if log.objective_id == objective.id]
                
                if not objective_logs:
                    goal_section += f"\nObjective: {objective.description}\n"
                    goal_section += "No data collected during this reporting period.\n"
                    continue
                
                # Calculate progress metrics
                progress_data = self._calculate_objective_progress(objective_logs)
                
                # Get goal-specific data from input
                objective_data = goals_data.get(str(objective.id), {})
                
                objective_section = self._generate_objective_section(
                    objective, progress_data, objective_data, objective_logs
                )
                
                goal_section += objective_section
            
            goals_section += goal_section
        
        return goals_section

    def _generate_objective_section(self, objective, progress_data, objective_data, trial_logs):
        """Generate detailed section for a specific objective."""
        
        section = f"\nObjective: {objective.description}\n"
        section += f"Target Accuracy: {objective.accuracy_target or 'Not specified'}\n\n"
        
        # Progress summary
        section += "Progress Summary:\n"
        section += f"  • Total Sessions: {progress_data['total_sessions']}\n"
        section += f"  • Total Trials: {progress_data['total_trials']}\n"
        section += f"  • Independence Rate: {progress_data['independence_rate']:.1f}%\n"
        section += f"  • Overall Accuracy: {progress_data['overall_accuracy']:.1f}%\n\n"
        
        # Support level breakdown
        section += "Support Level Distribution:\n"
        for level, count in progress_data['support_breakdown'].items():
            percentage = (count / progress_data['total_trials'] * 100) if progress_data['total_trials'] > 0 else 0
            section += f"  • {level.replace('_', ' ').title()}: {count} trials ({percentage:.1f}%)\n"
        
        # Progress trend
        if len(trial_logs) >= 3:
            trend = self._calculate_progress_trend(trial_logs)
            section += f"\nProgress Trend: {trend}\n"
        
        # Cue hierarchy analysis
        cue_analysis = self._analyze_cue_hierarchy(trial_logs)
        if cue_analysis:
            section += f"\nCue Hierarchy Analysis:\n{cue_analysis}\n"
        
        # Clinical notes from input data
        if objective_data.get('clinical_notes'):
            section += f"\nClinical Notes: {objective_data['clinical_notes']}\n"
        
        # Recommendations
        recommendations = self._generate_objective_recommendations(progress_data, objective_data)
        if recommendations:
            section += f"\nRecommendations: {recommendations}\n"
        
        section += "\n" + "-" * 40 + "\n"
        
        return section

    def _calculate_objective_progress(self, trial_logs):
        """Calculate comprehensive progress metrics for an objective."""
        
        if not trial_logs:
            return {
                'total_sessions': 0,
                'total_trials': 0,
                'independence_rate': 0,
                'overall_accuracy': 0,
                'support_breakdown': {},
                'sessions_with_data': 0
            }
        
        # Group by session date
        sessions_data = {}
        for log in trial_logs:
            date_key = log.session_date
            if date_key not in sessions_data:
                sessions_data[date_key] = []
            sessions_data[date_key].append(log)
        
        total_trials = sum(log.total_trials_new() for log in trial_logs)
        independent_trials = sum(log.independent for log in trial_logs)
        correct_trials = sum(
            log.independent + log.minimal_support + 
            log.moderate_support + log.maximal_support 
            for log in trial_logs
        )
        
        # Support level breakdown
        support_breakdown = {
            'independent': sum(log.independent for log in trial_logs),
            'minimal_support': sum(log.minimal_support for log in trial_logs),
            'moderate_support': sum(log.moderate_support for log in trial_logs),
            'maximal_support': sum(log.maximal_support for log in trial_logs),
            'incorrect': sum(log.incorrect for log in trial_logs)
        }
        
        return {
            'total_sessions': len(sessions_data),
            'total_trials': total_trials,
            'independence_rate': (independent_trials / total_trials * 100) if total_trials > 0 else 0,
            'overall_accuracy': (correct_trials / total_trials * 100) if total_trials > 0 else 0,
            'support_breakdown': support_breakdown,
            'sessions_with_data': len(sessions_data)
        }

    def _calculate_progress_trend(self, trial_logs):
        """Calculate progress trend over time."""
        
        # Group by session date and calculate independence rate for each
        daily_rates = {}
        for log in trial_logs:
            date_key = log.session_date
            if date_key not in daily_rates:
                daily_rates[date_key] = {'independent': 0, 'total': 0}
            
            daily_rates[date_key]['independent'] += log.independent
            daily_rates[date_key]['total'] += log.total_trials_new()
        
        # Calculate independence percentage for each day
        dates = sorted(daily_rates.keys())
        if len(dates) < 3:
            return "Insufficient data for trend analysis"
        
        rates = []
        for date in dates:
            if daily_rates[date]['total'] > 0:
                rate = daily_rates[date]['independent'] / daily_rates[date]['total'] * 100
                rates.append(rate)
        
        if len(rates) < 3:
            return "Insufficient data for trend analysis"
        
        # Simple trend calculation
        first_third = sum(rates[:len(rates)//3]) / (len(rates)//3)
        last_third = sum(rates[-len(rates)//3:]) / (len(rates)//3)
        
        difference = last_third - first_third
        
        if difference > 10:
            return "Improving trend (significant improvement noted)"
        elif difference > 5:
            return "Improving trend (moderate improvement noted)"
        elif difference > -5:
            return "Stable trend (consistent performance)"
        elif difference > -10:
            return "Declining trend (some decrease noted)"
        else:
            return "Declining trend (significant decrease noted)"

    def _analyze_cue_hierarchy(self, trial_logs):
        """Analyze movement through cue hierarchy."""
        
        if len(trial_logs) < 2:
            return None
        
        # Sort logs by date
        sorted_logs = sorted(trial_logs, key=lambda x: x.session_date)
        
        # Calculate primary support level for first and last sessions
        first_log = sorted_logs[0]
        last_log = sorted_logs[-1]
        
        def get_primary_support(log):
            support_counts = {
                'independent': log.independent,
                'minimal_support': log.minimal_support,
                'moderate_support': log.moderate_support,
                'maximal_support': log.maximal_support
            }
            return max(support_counts, key=support_counts.get)
        
        first_support = get_primary_support(first_log)
        last_support = get_primary_support(last_log)
        
        hierarchy_index = {level: i for i, level in enumerate(self.cue_hierarchy)}
        
        if hierarchy_index[last_support] < hierarchy_index[first_support]:
            return f"Positive movement through cue hierarchy from {first_support.replace('_', ' ')} to {last_support.replace('_', ' ')}"
        elif hierarchy_index[last_support] > hierarchy_index[first_support]:
            return f"Requires increased support: moved from {first_support.replace('_', ' ')} to {last_support.replace('_', ' ')}"
        else:
            return f"Consistent performance at {first_support.replace('_', ' ')} level"

    def _generate_objective_recommendations(self, progress_data, objective_data):
        """Generate recommendations for an objective."""
        
        independence_rate = progress_data['independence_rate']
        
        if independence_rate >= 80:
            return "Consider advancing to next target or increasing complexity. Begin fading support."
        elif independence_rate >= 60:
            return "Continue current intervention. Begin reducing support level gradually."
        elif independence_rate >= 40:
            return "Maintain current approach. Consider additional practice opportunities."
        elif independence_rate >= 20:
            return "May need strategy modification or increased support. Review intervention approach."
        else:
            return "Consider baseline reassessment or intervention modification."

    def _generate_summary_section(self, student, trial_logs, sessions):
        """Generate overall summary section."""
        
        if not trial_logs:
            return "\nOVERALL SUMMARY\n\nNo trial data available for this reporting period."
        
        # Calculate overall metrics
        total_trials = sum(log.total_trials_new() for log in trial_logs)
        independent_trials = sum(log.independent for log in trial_logs)
        overall_independence = (independent_trials / total_trials * 100) if total_trials > 0 else 0
        
        # Determine progress descriptor
        progress_descriptor = "minimal progress"
        for threshold in sorted(self.progress_descriptors.keys(), reverse=True):
            if overall_independence >= threshold:
                progress_descriptor = self.progress_descriptors[threshold]
                break
        
        summary = f"""
OVERALL SUMMARY

{student.first_name} demonstrated {progress_descriptor} during this {len(sessions)}-session reporting period. 
Across all goals and objectives, {student.pronouns.split('/')[0] if student.pronouns else 'they'} achieved an overall independence rate of {overall_independence:.1f}% 
over {total_trials} total trials.

Key Highlights:
• Total therapy sessions completed: {len(sessions)}
• Total trials across all objectives: {total_trials}
• Overall independence rate: {overall_independence:.1f}%
• Primary areas of focus: {', '.join([goal.description[:50] + '...' if len(goal.description) > 50 else goal.description for goal in student.goals if goal.active][:3])}
"""
        
        return summary

    def _generate_recommendations(self, student, trial_logs, goals_data):
        """Generate recommendations section."""
        
        recommendations = "\nRECOMMendations FOR CONTINUED SERVICES\n\n"
        
        if not trial_logs:
            recommendations += f"{student.first_name} would benefit from continued speech-language therapy services to address identified goals."
            return recommendations
        
        # Calculate overall progress
        total_trials = sum(log.total_trials_new() for log in trial_logs)
        independent_trials = sum(log.independent for log in trial_logs)
        overall_independence = (independent_trials / total_trials * 100) if total_trials > 0 else 0
        
        if overall_independence >= 80:
            recommendations += f"Consider transition planning and generalization activities. {student.first_name} is demonstrating strong independence."
        elif overall_independence >= 60:
            recommendations += f"Continue current intervention with focus on independence. {student.first_name} is making good progress."
        elif overall_independence >= 40:
            recommendations += f"Maintain current frequency of services. Consider strategy modifications to improve independence."
        else:
            recommendations += f"Consider intervention modifications or increased frequency of services."
        
        # Add specific recommendations from goals data
        for goal_data in goals_data.values():
            if goal_data.get('recommendations'):
                recommendations += f"\n• {goal_data['recommendations']}"
        
        recommendations += f"\n\nRecommended continuation of speech-language therapy services at current frequency."
        
        return recommendations

    def _compile_report(self, sections):
        """Compile all sections into final report."""
        
        report = sections['header']
        report += "\n\n" + sections['attendance']
        report += "\n\n" + sections['goals']
        report += "\n\n" + sections['summary'] 
        report += "\n\n" + sections['recommendations']
        
        return report

    def _get_quarter_dates(self, quarter, year):
        """Get start and end dates for a quarter."""
        
        months = self.quarters[quarter]['months']
        start_date = date(year, months[0], 1)
        
        # Last day of last month in quarter
        last_month = months[-1]
        last_day = calendar.monthrange(year, last_month)[1]
        end_date = date(year, last_month, last_day)
        
        return start_date, end_date

    def _get_quarter_from_date(self, date_obj):
        """Determine quarter from a date."""
        month = date_obj.month
        for quarter, data in self.quarters.items():
            if month in data['months']:
                return quarter
        return 'Q1'

    def get_available_quarters(self, year=None):
        """Get list of available quarters for selection."""
        if year is None:
            year = date.today().year
            
        return [
            {'code': f'Q1', 'name': f'Q1 {year}', 'months': 'Jan-Mar'},
            {'code': f'Q2', 'name': f'Q2 {year}', 'months': 'Apr-Jun'},
            {'code': f'Q3', 'name': f'Q3 {year}', 'months': 'Jul-Sep'},
            {'code': f'Q4', 'name': f'Q4 {year}', 'months': 'Oct-Dec'}
        ]

# API Integration
from flask import Blueprint, request, jsonify
from auth.decorators import require_auth, require_permission

reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/api/reports/quarterly/generate', methods=['POST'])
@require_auth
@require_permission('write')
def generate_quarterly_report():
    """Generate quarterly progress report."""
    
    try:
        data = request.json
        student_id = data['student_id']
        quarter = data['quarter']
        year = data['year']
        goals_data = data.get('goals_data', {})
        
        generator = QuarterlyReportGenerator()
        report = generator.generate_report(student_id, quarter, year, goals_data)
        
        return jsonify(report)
        
    except Exception as e:
        current_app.logger.error(f'Error generating quarterly report: {str(e)}')
        return jsonify({'error': 'Failed to generate quarterly report'}), 500

@reports_bp.route('/api/reports/quarterly/history/<int:student_id>')
@require_auth
def get_quarterly_report_history(student_id):
    """Get historical quarterly reports for a student."""
    
    try:
        reports = QuarterlyReport.query.filter_by(
            student_id=student_id
        ).order_by(QuarterlyReport.created_at.desc()).all()
        
        return jsonify({
            'reports': [report.to_dict() for report in reports]
        })
        
    except Exception as e:
        current_app.logger.error(f'Error retrieving report history: {str(e)}')
        return jsonify({'error': 'Failed to retrieve report history'}), 500
