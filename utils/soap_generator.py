# utils/soap_generator.py - Smart SOAP note generation
from models import Student, TrialLog, Session
from datetime import datetime

# TODO: Add Activity model import if/when the model is implemented

class SOAPGenerator:
    """Advanced SOAP note generation with smart templates and pronoun handling."""
    
    def __init__(self):
        self.templates = {
            'subjective': {
                'positive': [
                    "{student} {pronoun_verb} excited to participate in today's session.",
                    "{student} {pronoun_verb} cooperative and engaged throughout the session.",
                    "{student} reported feeling confident about {pronoun_possessive} progress.",
                    "{student} {pronoun_verb} motivated and eager to work on speech goals.",
                    "{student} demonstrated good attention and focus during activities."
                ],
                'neutral': [
                    "{student} participated in today's speech therapy session.",
                    "{student} {pronoun_verb} present for a {session_duration}-minute session.",
                    "{student} worked on {pronoun_possessive} speech and language goals.",
                    "{student} completed planned activities with varying levels of support."
                ],
                'challenging': [
                    "{student} required additional motivation to participate fully.",
                    "{student} {pronoun_verb} distracted but completed most activities.",
                    "{student} needed frequent redirection during the session.",
                    "{student} showed some resistance to certain activities."
                ]
            },
            'objective': {
                'articulation': [
                    "Targeted {sound} production in {word_level} with {accuracy}% accuracy.",
                    "Worked on {sound} in {position} position with {cue_type} cues.",
                    "Practiced {sound} discrimination tasks with {support_level} support.",
                    "Drilled {sound} production using {activity_type} activities."
                ],
                'language': [
                    "Addressed {language_skill} using {activity_type} activities.",
                    "Worked on {language_target} with {accuracy}% accuracy across {trials} trials.",
                    "Practiced {language_skill} in {context} context.",
                    "Targeted {grammar_structure} with {support_level} support."
                ],
                'fluency': [
                    "Worked on fluency strategies including {strategies}.",
                    "Practiced speech rate control with {accuracy}% success.",
                    "Addressed secondary behaviors through {intervention_type}.",
                    "Worked on easy onset and light contacts."
                ]
            },
            'assessment': {
                'progress': [
                    "{student} demonstrated {progress_level} progress toward speech goals.",
                    "Current performance indicates {progress_description}.",
                    "{student} is {making_progress} on targeted objectives.",
                    "Skills are {skill_status} at the current level of support."
                ],
                'recommendations': [
                    "Continue current intervention approach.",
                    "Increase difficulty level for targeted skills.",
                    "Focus on generalization to natural contexts.",
                    "Maintain current frequency of sessions."
                ]
            },
            'plan': [
                "Continue working on {target_skills} in future sessions.",
                "Increase independence by reducing {current_cues}.",
                "Begin targeting {next_target} in upcoming sessions.",
                "Provide home practice activities for {skill_area}.",
                "Schedule progress review in {timeframe}."
            ]
        }
        
        self.pronoun_mappings = {
            'he/him': {
                'subject': 'he',
                'object': 'him', 
                'possessive': 'his',
                'verb_was': 'was',
                'verb_has': 'has'
            },
            'she/her': {
                'subject': 'she',
                'object': 'her',
                'possessive': 'her', 
                'verb_was': 'was',
                'verb_has': 'has'
            },
            'they/them': {
                'subject': 'they',
                'object': 'them',
                'possessive': 'their',
                'verb_was': 'were',
                'verb_has': 'have'
            }
        }
        
        self.cue_types = {
            'visual': ['visual cues', 'visual prompts', 'visual models'],
            'verbal': ['verbal cues', 'verbal prompts', 'verbal models'],
            'tactile': ['tactile cues', 'tactile prompts'],
            'gestural': ['gestural cues', 'hand signals'],
            'combined': ['visual and verbal cues', 'multimodal prompts']
        }
        
        self.support_levels = {
            'independent': 'independent performance',
            'minimal_support': 'minimal support/cueing',
            'moderate_support': 'moderate support/cueing', 
            'maximal_support': 'maximal support/cueing'
        }

    def generate_soap_note(self, student_id, session_date, session_data, trial_logs_data=None):
        """Generate complete SOAP note with smart templates."""
        
        student = Student.query.get_or_404(student_id)
        session = Session.query.filter_by(
            student_id=student_id,
            session_date=session_date
        ).first()
        
        # Get trial logs for this session
        trial_logs = TrialLog.query.filter_by(
            student_id=student_id,
            session_date=session_date
        ).all()
        
        # Generate each SOAP section
        subjective = self._generate_subjective(student, session, session_data)
        objective = self._generate_objective(student, trial_logs, session_data)
        assessment = self._generate_assessment(student, trial_logs, session_data)
        plan = self._generate_plan(student, session_data)
        
        return {
            'subjective': subjective,
            'objective': objective, 
            'assessment': assessment,
            'plan': plan,
            'generated_at': datetime.now().isoformat(),
            'student_name': student.display_name
        }

    def _generate_subjective(self, student, session, session_data):
        """Generate subjective section with mood and engagement info."""
        
        mood = session_data.get('mood', 'neutral')
        pronouns = self._get_pronouns(student.pronouns)
        
        # Select template based on mood
        templates = self.templates['subjective'][mood]
        base_template = session_data.get('subjective_template') or templates[0]
        
        # Fill in template
        subjective = base_template.format(
            student=student.first_name,
            pronoun_subject=pronouns['subject'],
            pronoun_object=pronouns['object'], 
            pronoun_possessive=pronouns['possessive'],
            pronoun_verb=pronouns['verb_was'],
            session_duration=session.duration_minutes if session else 30
        )
        
        # Add custom notes if provided
        if session_data.get('subjective_notes'):
            subjective += f" {session_data['subjective_notes']}"
            
        return subjective

    def _generate_objective(self, student, trial_logs, session_data):
        """Generate objective section with trial data and activities."""
        
        objective_parts = []
        
        # Process each goal area
        for area_data in session_data.get('goal_areas', []):
            area_type = area_data.get('type', 'language')
            
            if area_type in self.templates['objective']:
                templates = self.templates['objective'][area_type]
                template = area_data.get('template') or templates[0]
                
                # Get trial data for this area
                area_trials = [log for log in trial_logs 
                             if log.objective and 
                             area_data.get('objective_id') == log.objective_id]
                
                accuracy = self._calculate_accuracy(area_trials)
                total_trials = sum(log.total_trials for log in area_trials)
                support_level = self._determine_support_level(area_trials)
                
                objective_text = template.format(
                    sound=area_data.get('target_sound', '[target]'),
                    word_level=area_data.get('word_level', 'word level'),
                    position=area_data.get('position', 'initial'),
                    accuracy=accuracy,
                    trials=total_trials,
                    cue_type=area_data.get('cue_type', 'verbal'),
                    support_level=support_level,
                    activity_type=area_data.get('activity', 'structured'),
                    language_skill=area_data.get('language_skill', 'vocabulary'),
                    language_target=area_data.get('language_target', 'target skill'),
                    context=area_data.get('context', 'structured'),
                    grammar_structure=area_data.get('grammar', 'sentences'),
                    strategies=area_data.get('strategies', 'easy onset'),
                    intervention_type=area_data.get('intervention', 'direct therapy')
                )
                
                objective_parts.append(objective_text)
        
        # Add activities used
        if session_data.get('activities'):
            activities_text = f"Activities included: {', '.join(session_data['activities'])}."
            objective_parts.append(activities_text)
            
        return ' '.join(objective_parts)

    def _generate_assessment(self, student, trial_logs, session_data):
        """Generate assessment section with progress analysis."""
        
        # Calculate overall progress
        if trial_logs:
            independence_rate = self._calculate_independence_rate(trial_logs) or 0

            if independence_rate >= 80:
                progress_level = "excellent"
                progress_description = "consistent independent performance"
            elif independence_rate >= 60:
                progress_level = "good"
                progress_description = "emerging independence with minimal support"
            elif independence_rate >= 40:
                progress_level = "moderate"
                progress_description = "progress with moderate support needed"
            else:
                progress_level = "emerging"
                progress_description = "early skill development with maximal support"
        else:
            independence_rate = 0
            progress_level = "baseline"
            progress_description = "baseline data collection"
        
        # Select assessment template
        templates = self.templates['assessment']['progress']
        assessment_template = session_data.get('assessment_template') or templates[0]
        
        assessment = assessment_template.format(
            student=student.first_name,
            progress_level=progress_level,
            progress_description=progress_description,
            making_progress="making progress" if independence_rate > 50 else "developing skills",
            skill_status="emerging" if independence_rate < 60 else "developing"
        )
        
        # Add custom assessment notes
        if session_data.get('assessment_notes'):
            assessment += f" {session_data['assessment_notes']}"
            
        return assessment

    def _generate_plan(self, student, session_data):
        """Generate plan section with next steps."""
        
        plan_parts = []
        
        # Add main plan template
        if session_data.get('plan_template'):
            plan_template = session_data['plan_template']
        else:
            plan_template = self.templates['plan'][0]
            
        plan_text = plan_template.format(
            target_skills=session_data.get('target_skills', 'speech and language goals'),
            current_cues=session_data.get('current_cues', 'verbal cues'),
            next_target=session_data.get('next_target', 'carryover activities'),
            skill_area=session_data.get('skill_area', 'targeted skills'),
            timeframe=session_data.get('review_timeframe', '4 weeks')
        )
        
        plan_parts.append(plan_text)
        
        # Add homework/carryover if specified
        if session_data.get('homework'):
            plan_parts.append(f"Home practice: {session_data['homework']}")
            
        # Add next session focus
        if session_data.get('next_session_focus'):
            plan_parts.append(f"Next session will focus on: {session_data['next_session_focus']}")
            
        return ' '.join(plan_parts)

    def _get_pronouns(self, pronoun_string):
        """Get pronoun mappings for a student."""
        if not pronoun_string:
            return self.pronoun_mappings['they/them']
            
        pronoun_string = pronoun_string.lower()
        return self.pronoun_mappings.get(pronoun_string, self.pronoun_mappings['they/them'])

    def _calculate_accuracy(self, trial_logs):
        """Calculate overall accuracy from trial logs."""
        if not trial_logs:
            return 0
            
        total_trials = sum(log.total_trials for log in trial_logs)
        correct_trials = sum(
            log.independent + log.minimal_support + 
            log.moderate_support + log.maximal_support 
            for log in trial_logs
        )
        
        return round((correct_trials / total_trials * 100)) if total_trials > 0 else 0

    def _calculate_independence_rate(self, trial_logs):
        """Calculate independence rate from trial logs."""
        if not trial_logs:
            return 0
            
        total_trials = sum(log.total_trials for log in trial_logs)
        independent_trials = sum(log.independent for log in trial_logs)
        
        return round((independent_trials / total_trials * 100)) if total_trials > 0 else 0

    def _determine_support_level(self, trial_logs):
        """Determine primary support level used."""
        if not trial_logs:
            return "baseline data collection"
            
        # Count support types
        support_counts = {
            'independent': sum(log.independent for log in trial_logs),
            'minimal': sum(log.minimal_support for log in trial_logs),
            'moderate': sum(log.moderate_support for log in trial_logs),
            'maximal': sum(log.maximal_support for log in trial_logs)
        }
        
        # Find most common support level
        max_support = max(support_counts, key=support_counts.get)
        return self.support_levels.get(max_support + '_support', 'varied support')

    def get_available_templates(self, section, category=None):
        """Get available templates for a SOAP section."""
        if section not in self.templates:
            return []
            
        if category and isinstance(self.templates[section], dict):
            return self.templates[section].get(category, [])
        elif isinstance(self.templates[section], list):
            return self.templates[section]
        else:
            return list(self.templates[section].keys())

    def customize_template(self, section, category, new_template):
        """Add a custom template to the system."""
        if section not in self.templates:
            self.templates[section] = {}
            
        if category:
            if not isinstance(self.templates[section], dict):
                self.templates[section] = {category: []}
            if category not in self.templates[section]:
                self.templates[section][category] = []
            self.templates[section][category].append(new_template)
        else:
            if not isinstance(self.templates[section], list):
                self.templates[section] = []
            self.templates[section].append(new_template)
