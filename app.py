from datetime import date, datetime
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-secret-key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///task_manager.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    tasks = db.relationship("Task", backref="user", lazy=True, cascade="all, delete-orphan")


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, default="")
    due_date = db.Column(db.Date, nullable=False)
    due_time = db.Column(db.Time, nullable=False, default=lambda: datetime.strptime("23:59", "%H:%M").time())
    status = db.Column(db.String(20), default="Pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def due_datetime(task):
    """Return the task's combined due date and time."""
    task_time = task.due_time or datetime.strptime("23:59", "%H:%M").time()
    return datetime.combine(task.due_date, task_time)


def is_overdue(task):
    """Return True when an unfinished task's exact due date/time has passed."""
    return task.status != "Completed" and due_datetime(task) < datetime.now()


@app.context_processor
def inject_helpers():
    return {"is_overdue": is_overdue, "due_datetime": due_datetime, "today": date.today()}


@app.route("/")
def index():
    return redirect(url_for("dashboard" if "user_id" in session else "login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not name or not email or not password:
            flash("Please fill in all required fields.", "danger")
            return render_template("register.html")
        if password != confirm:
            flash("Passwords do not match.", "danger")
            return render_template("register.html")
        if len(password) < 6:
            flash("Password must contain at least 6 characters.", "danger")
            return render_template("register.html")
        if User.query.filter_by(email=email).first():
            flash("An account with this email already exists.", "danger")
            return render_template("register.html")

        user = User(name=name, email=email, password=generate_password_hash(password, method="pbkdf2:sha256"))
        db.session.add(user)
        db.session.commit()
        flash("Account created successfully. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            session.clear()
            session["user_id"] = user.id
            session["user_name"] = user.name
            flash("Welcome back!", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    status_filter = request.args.get("status", "All")
    search = request.args.get("search", "").strip()

    query = Task.query.filter_by(user_id=user_id)

    if search:
        query = query.filter(Task.title.ilike(f"%{search}%"))

    if status_filter == "Pending":
        query = query.filter(Task.status == "Pending")
    elif status_filter == "Completed":
        query = query.filter(Task.status == "Completed")
    elif status_filter == "Overdue":
        # Overdue is evaluated with both date and time below; fetch pending tasks first.
        query = query.filter(Task.status != "Completed")

    tasks = query.order_by(Task.due_date.asc(), Task.due_time.asc(), Task.created_at.desc()).all()
    if status_filter == "Overdue":
        tasks = [t for t in tasks if is_overdue(t)]
    all_tasks = Task.query.filter_by(user_id=user_id).all()

    total = len(all_tasks)
    completed = sum(t.status == "Completed" for t in all_tasks)
    pending = sum(t.status == "Pending" for t in all_tasks)
    overdue = sum(t.status != "Completed" and is_overdue(t) for t in all_tasks)

    stats = {"total": total, "completed": completed, "pending": pending, "overdue": overdue}

    return render_template(
        "dashboard.html",
        tasks=tasks,
        stats=stats,
        status_filter=status_filter,
        search=search,
    )


@app.route("/task/add", methods=["GET", "POST"])
@login_required
def add_task():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        due_date_raw = request.form.get("due_date", "")
        due_time_raw = request.form.get("due_time", "")
        status = request.form.get("status", "Pending")

        if not title or not due_date_raw or not due_time_raw:
            flash("Task name, completion date and time are required.", "danger")
            return render_template("task_form.html", task=None, page_title="Add Task")

        try:
            due_date = datetime.strptime(due_date_raw, "%Y-%m-%d").date()
            due_time = datetime.strptime(due_time_raw, "%H:%M").time()
        except ValueError:
            flash("Please enter a valid date and time.", "danger")
            return render_template("task_form.html", task=None, page_title="Add Task")

        task = Task(
            user_id=session["user_id"],
            title=title,
            description=description,
            due_date=due_date,
            due_time=due_time,
            status="Completed" if status == "Completed" else "Pending",
            completed_at=datetime.utcnow() if status == "Completed" else None,
        )
        db.session.add(task)
        db.session.commit()
        flash("Task added successfully.", "success")
        return redirect(url_for("dashboard"))

    return render_template("task_form.html", task=None, page_title="Add Task")


@app.route("/task/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def edit_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=session["user_id"]).first_or_404()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        due_date_raw = request.form.get("due_date", "")
        due_time_raw = request.form.get("due_time", "")
        status = request.form.get("status", "Pending")

        if not title or not due_date_raw or not due_time_raw:
            flash("Task name, completion date and time are required.", "danger")
            return render_template("task_form.html", task=task, page_title="Edit Task")

        try:
            due_date = datetime.strptime(due_date_raw, "%Y-%m-%d").date()
            due_time = datetime.strptime(due_time_raw, "%H:%M").time()
        except ValueError:
            flash("Please enter a valid date and time.", "danger")
            return render_template("task_form.html", task=task, page_title="Edit Task")

        task.title = title
        task.description = description
        task.due_date = due_date
        task.due_time = due_time
        task.status = "Completed" if status == "Completed" else "Pending"
        task.completed_at = datetime.utcnow() if task.status == "Completed" else None

        db.session.commit()
        flash("Task updated successfully.", "success")
        return redirect(url_for("dashboard"))

    return render_template("task_form.html", task=task, page_title="Edit Task")


@app.post("/task/<int:task_id>/complete")
@login_required
def complete_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=session["user_id"]).first_or_404()
    task.status = "Completed"
    task.completed_at = datetime.utcnow()
    db.session.commit()
    flash("Task marked as completed.", "success")
    return redirect(url_for("dashboard"))


@app.post("/task/<int:task_id>/delete")
@login_required
def delete_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=session["user_id"]).first_or_404()
    db.session.delete(task)
    db.session.commit()
    flash("Task deleted.", "success")
    return redirect(url_for("dashboard"))


@app.route("/profile")
@login_required
def profile():
    user = User.query.get_or_404(session["user_id"])
    return render_template("profile.html", user=user)


with app.app_context():
    db.create_all()
    # Upgrade an existing database created by the previous version.
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    columns = {column["name"] for column in inspector.get_columns("task")}
    if "due_time" not in columns:
        with db.engine.begin() as connection:
            connection.execute(text("ALTER TABLE task ADD COLUMN due_time TIME DEFAULT '23:59:00'"))



if __name__ == "__main__":
    app.run(debug=True)
