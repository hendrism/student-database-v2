# student-database-v2

## Project Overview
student-database-v2 is a Flask-based web application designed to manage student information efficiently. It leverages SQLAlchemy for database modeling and provides a comprehensive set of features including student records management, session tracking, SOAP notes, calendar integration, and report generation. The application supports authentication which can be toggled for development convenience.

## Features
- **Student Management:** Create, read, update, and delete student records.
- **Session Tracking:** Manage and log student sessions.
- **SOAP Notes:** Maintain SOAP (Subjective, Objective, Assessment, Plan) notes for students.
- **Calendar Integration:** View and manage appointments and important dates.
- **Reports:** Generate reports based on student data and sessions.
- **Authentication:** Secure access to the application with optional authentication that can be disabled via environment variable.
- **Utilities:** Helper functions and tools to support application functionality.

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/student-database-v2.git
   cd student-database-v2
   ```

2. Create and activate a virtual environment:
   ```
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

## Usage

1. Set up environment variables as needed. To disable authentication during development, set:
   ```
   export AUTH_DISABLED=true
   ```
   On Windows (PowerShell):
   ```
   setx AUTH_DISABLED true
   ```

2. Run the Flask application:
   ```
   flask run
   ```
   The app will be available at `http://localhost:5000`.

3. Use the provided routes to interact with the app:
   - `/students` - Manage student records
   - `/sessions` - Manage student sessions
   - `/soap` - Access SOAP notes
   - `/calendar` - View calendar events
   - `/reports` - Generate and view reports

## Development

- The application uses Flask and SQLAlchemy for backend development.
- Authentication can be toggled via the `AUTH_DISABLED` environment variable for easier testing.
- Routes are organized by functionality for maintainability.
- Utilities provide common helper functions.

To start development, ensure your virtual environment is activated and dependencies are installed. Run the app with debug mode enabled:
```
export FLASK_ENV=development
flask run
```

## Testing

Run tests using your preferred testing framework. If using `pytest`, simply execute:
```
pytest
```
Ensure your test environment is set up and dependencies are installed.

## License

This project is licensed under the MIT License. See the LICENSE file for details.
