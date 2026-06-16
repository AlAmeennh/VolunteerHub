from flask import Flask, render_template, redirect, url_for, request, flash, session, Response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import csv, io

app = Flask(__name__)
app.config['SECRET_KEY'] = 'change-this-secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///volunteers.db'
db = SQLAlchemy(app)


# ---------- Models ----------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)


class Volunteer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    skills = db.Column(db.String(200))
    availability = db.Column(db.String(50))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))


# ---------- Decorators ----------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            flash('Admin access required.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated


# ---------- Auth Routes ----------

@app.route('/')
def index():
    return redirect(url_for('dashboard') if session.get('is_admin') else url_for('volunteer_form'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'warning')
        else:
            db.session.add(User(username=username, password=generate_password_hash(password)))
            db.session.commit()
            flash('Registered! Please log in.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username'].strip()).first()
        if user and check_password_hash(user.password, request.form['password']):
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            return redirect(url_for('index'))
        flash('Invalid credentials.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ---------- Volunteer Routes ----------

@app.route('/volunteer', methods=['GET', 'POST'])
@login_required
def volunteer_form():
    existing = Volunteer.query.filter_by(user_id=session['user_id']).first()
    if request.method == 'POST':
        data = {k: request.form[k].strip() for k in ['name', 'email', 'phone', 'skills', 'availability']}
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
        else:
            if Volunteer.query.filter_by(email=data['email']).first():
                flash('Email already registered.', 'warning')
                return render_template('volunteer_form.html', v=existing)
            db.session.add(Volunteer(**data, user_id=session['user_id']))
        db.session.commit()
        flash('Volunteer info saved!', 'success')
        return redirect(url_for('volunteer_form'))
    return render_template('volunteer_form.html', v=existing)


# ---------- Admin Routes ----------

@app.route('/dashboard')
@login_required
@admin_required
def dashboard():
    volunteers = Volunteer.query.all()
    return render_template('dashboard.html', volunteers=volunteers)


@app.route('/edit/<int:vid>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_volunteer(vid):
    v = Volunteer.query.get_or_404(vid)
    if request.method == 'POST':
        for field in ['name', 'email', 'phone', 'skills', 'availability']:
            setattr(v, field, request.form[field].strip())
        db.session.commit()
        flash('Volunteer updated.', 'success')
        return redirect(url_for('dashboard'))
    return render_template('volunteer_form.html', v=v, edit=True)


@app.route('/delete/<int:vid>', methods=['POST'])
@login_required
@admin_required
def delete_volunteer(vid):
    db.session.delete(Volunteer.query.get_or_404(vid))
    db.session.commit()
    flash('Volunteer deleted.', 'info')
    return redirect(url_for('dashboard'))


@app.route('/export')
@login_required
@admin_required
def export_csv():
    volunteers = Volunteer.query.all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Name', 'Email', 'Phone', 'Skills', 'Availability'])
    for v in volunteers:
        writer.writerow([v.id, v.name, v.email, v.phone, v.skills, v.availability])
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=volunteers.csv'})


# ---------- Init ----------

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Create default admin if none exists
        if not User.query.filter_by(username='admin').first():
            db.session.add(User(username='admin',
                                password=generate_password_hash('admin123'),
                                is_admin=True))
            db.session.commit()
    app.run(debug=True)
