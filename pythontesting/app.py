import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import CSRFProtect, FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired, Length

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET', 'dev-secret')
print(f"Using secret key: {app.config['SECRET_KEY']} (debug={app.debug})")
if not app.debug and app.config['SECRET_KEY'] == 'dev-secret':
    raise Exception(
        'In production, set a strong FLASK_SECRET environment variable!')

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + \
    os.path.join(BASE_DIR, 'app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    WTF_CSRF_TIME_LIMIT=None,
)

# Make secure cookie usage configurable for local testing
use_secure = os.environ.get('USE_SECURE_COOKIES', '1') == '1'
app.config['SESSION_COOKIE_SECURE'] = use_secure

# Session lifetime
app.permanent_session_lifetime = timedelta(
    hours=int(os.environ.get('SESSION_HOURS', '1')))

db = SQLAlchemy(app)
csrf = CSRFProtect(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    failed_logins = db.Column(db.Integer, default=0, nullable=False)
    last_failed_at = db.Column(db.DateTime, nullable=True)
    locked_until = db.Column(db.DateTime, nullable=True)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


with app.app_context():
    db.create_all()


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[
                           DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Password', validators=[
                             DataRequired(), Length(min=6, max=128)])


class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[
                           DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Password', validators=[
                             DataRequired(), Length(min=6, max=128)])


@app.route('/')
def index():
    user_id = session.get('user_id')
    if user_id:
        user = User.query.get(user_id)
        return render_template('dashboard.html', user=user)

    form = LoginForm()
    return render_template('login.html', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data.strip() if form.username.data else ''
        password = form.password.data

        if not password:
            flash('Password is required.', 'danger')
            return redirect(url_for('register'))

        existing = User.query.filter_by(username=username).first()
        if existing:
            flash('Username already taken.', 'danger')
            return redirect(url_for('register'))

        user = User()
        user.username = username
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Account created. Please log in.', 'success')
        return redirect(url_for('index'))

    return render_template('register.html', form=form)


@app.route('/login', methods=['POST'])
def login():
    form = LoginForm()
    if not form.validate_on_submit():
        flash('Invalid input.', 'danger')
        return redirect(url_for('index'))

    username = form.username.data.strip() if form.username.data else ''
    password = form.password.data
    user = User.query.filter_by(username=username).first()
    now = datetime.utcnow()

    # Check account lockout
    if user and user.locked_until and user.locked_until > now:
        flash('Account locked due to multiple failed attempts. Try again later.', 'danger')
        return redirect(url_for('index'))

    # Verify credentials
    if not user or not user.check_password(password):
        if user:
            user.failed_logins = (user.failed_logins or 0) + 1
            user.last_failed_at = now
            # Lock account after 5 failed attempts
            if user.failed_logins >= 5:
                user.locked_until = now + timedelta(minutes=15)
                user.failed_logins = 0
            db.session.add(user)
            db.session.commit()

        flash('Invalid username or password.', 'danger')
        return redirect(url_for('index'))

    # Successful login: reset counters and rotate session
    user.failed_logins = 0
    user.last_failed_at = None
    user.locked_until = None
    db.session.add(user)
    db.session.commit()

    session.clear()
    session.permanent = True
    session['user_id'] = user.id
    flash('Logged in successfully.', 'success')
    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logged out.', 'info')
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
