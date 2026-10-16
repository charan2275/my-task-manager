# My Task Manager

A clean full-stack task management web application built for the college project abstract.

## Features

- User registration and login
- Secure password hashing
- User-specific task dashboard
- Add, edit and delete tasks
- Mark tasks as completed
- Completion date
- Automatic overdue detection
- Search tasks
- Filter by All / Pending / Completed / Overdue
- Dashboard statistics
- Responsive modern interface
- SQLite database

## Technology

- Python
- Flask
- Flask-SQLAlchemy
- SQLite
- HTML
- CSS
- Bootstrap 5
- Jinja2
- JavaScript

## Run on macOS / Linux

```bash
cd my_task_manager
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Open:

http://127.0.0.1:5000

The SQLite database `task_manager.db` is created automatically on first run.

## Important

For a real deployment, change the Flask `SECRET_KEY` to a strong random value and use environment variables.
