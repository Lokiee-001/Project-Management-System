from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user
)
from werkzeug.security import generate_password_hash, check_password_hash

# ---------------- APP CONFIG ----------------

app = Flask(__name__)

app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pms.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SERVER_NAME'] = 'localhost:5000'

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


# ---------------- MODELS ----------------

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    user_id = db.Column(db.Integer,
                        db.ForeignKey('user.id'),
                        nullable=False)


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(50), default="To Do")
    project_id = db.Column(db.Integer,
                           db.ForeignKey('project.id'),
                           nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---- Helper: AI insight generator (centralized for both routes)
def generate_ai_insight(percent, todo, total):
    if total == 0:
        return "No tasks available."
    if percent == 100:
        return "Project completed successfully."
    elif percent >= 60:
        return "Project progressing well."
    elif percent >= 30:
        return "Moderate progress."
    else:
        return "Project needs attention."


# ---------------- AUTH ROUTES ----------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user_exists = User.query.filter_by(username=username).first()

        if user_exists:
            flash("Username already exists")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)

        new_user = User(
            username=username,
            password=hashed_password
        )

        db.session.add(new_user)
        db.session.commit()

        flash("Registration Successful")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("dashboard"))

        flash("Invalid Credentials")

    return render_template("login.html")


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ---------------- DASHBOARD ----------------

@app.route('/')
@login_required
def dashboard():
    projects = Project.query.filter_by(
        user_id=current_user.id
    ).all()

    return render_template(
        "dashboard.html",
        projects=projects
    )


@app.route('/developer')
@login_required
def developer():
    return render_template('developer.html')


# ---------------- PROJECT ROUTES ----------------

@app.route('/create_project', methods=['POST'])
@login_required
def create_project():

    name = request.form.get("name")
    description = request.form.get("description")

    project = Project(
        name=name,
        description=description,
        user_id=current_user.id
    )

    db.session.add(project)
    db.session.commit()

    return redirect(url_for("dashboard"))


@app.route('/delete_project/<int:project_id>')
@login_required
def delete_project(project_id):

    project = Project.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        return "Unauthorized", 403

    db.session.delete(project)
    db.session.commit()

    return redirect(url_for("dashboard"))


# ---------------- VIEW PROJECT ----------------

@app.route('/project/<int:project_id>')
@login_required
def view_project(project_id):

    project = Project.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        return "Unauthorized", 403

    tasks = Task.query.filter_by(
        project_id=project.id
    ).all()

    return render_template(
        "project.html",
        project=project,
        tasks=tasks
    )


# ---------------- TASK ROUTES ----------------

@app.route('/add_task/<int:project_id>', methods=['POST'])
@login_required
def add_task(project_id):

    project = Project.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        return "Unauthorized", 403

    title = request.form.get("title")
    description = request.form.get("description")

    task = Task(
        title=title,
        description=description,
        project_id=project.id
    )

    db.session.add(task)
    db.session.commit()

    return redirect(url_for(
        "view_project",
        project_id=project.id
    ))


@app.route('/delete_task/<int:task_id>')
@login_required
def delete_task(task_id):

    task = Task.query.get_or_404(task_id)
    project = Project.query.get(task.project_id)

    if project.user_id != current_user.id:
        return "Unauthorized", 403

    db.session.delete(task)
    db.session.commit()

    return redirect(url_for(
        "view_project",
        project_id=project.id
    ))


@app.route('/update_status/<int:task_id>/<string:new_status>')
@login_required
def update_status(task_id, new_status):

    task = Task.query.get_or_404(task_id)
    project = Project.query.get(task.project_id)

    if project.user_id != current_user.id:
        return "Unauthorized", 403

    task.status = new_status
    db.session.commit()

    return redirect(url_for(
        "view_project",
        project_id=project.id
    ))

@app.route("/summary/<int:project_id>")
def summary(project_id):

    project = Project.query.get(project_id)

    tasks = Task.query.filter_by(project_id=project_id).all()

    total = len(tasks)
    completed = len([t for t in tasks if t.status == "Completed"])
    in_progress = len([t for t in tasks if t.status == "In Progress"])
    todo = len([t for t in tasks if t.status == "Pending"])

    percent = int((completed / total) * 100) if total > 0 else 0

    insight = generate_ai_insight(percent, todo, total)

    return render_template(
        "summary.html",
        project=project,
        total=total,
        completed=completed,
        in_progress=in_progress,
        todo=todo,
        percent=percent,
        insight=insight
    )

# ================= AI SUMMARY (UPDATED ONLY) =================
@app.route('/generate_summary/<int:project_id>')
@login_required
def generate_summary(project_id):

    project = Project.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        return "Unauthorized", 403

    tasks = Task.query.filter_by(project_id=project.id).all()

    # ---- COUNT TASKS ----
    total = len(tasks)
    completed = 0
    in_progress = 0
    todo = 0

    for task in tasks:
        if task.status == "Done":
            completed += 1
        elif task.status == "In Progress":
            in_progress += 1
        else:
            todo += 1

    # ---- ALWAYS DEFINE PERCENT ----
    percent = 0

    if total > 0:
        percent = round((completed / total) * 100)

    # ---- AI INSIGHT ----
    if percent == 100:
        insight = "Project completed successfully."
    elif percent >= 60:
        insight = "Project progressing well."
    elif percent >= 30:
        insight = "Moderate progress."
    elif total == 0:
        insight = "No tasks available."
    else:
        insight = "Project needs attention."

    # ---- SEND DATA TO HTML ----
    return render_template(
        "summary.html",
        project=project,
        total=total,
        completed=completed,
        in_progress=in_progress,
        todo=todo,
        percent=percent,
        insight=insight
    )
# ---------------- RUN APP ----------------

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app.run(debug=True)