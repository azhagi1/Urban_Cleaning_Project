from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from email_utils import generate_code, send_verification_code
from config import SQLALCHEMY_DATABASE_URI, SECRET_KEY

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SECRET_KEY'] = SECRET_KEY

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

verification_codes = {}

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80))
    email = db.Column(db.String(120), unique=True)
    phone = db.Column(db.String(15))
    password = db.Column(db.String(200))
    is_verified = db.Column(db.Boolean, default=False)

class ServiceProvider(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    service_type = db.Column(db.String(100))
    contact = db.Column(db.String(100))

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    services = db.Column(db.String(255))
    date = db.Column(db.String(50))
    time = db.Column(db.String(50))

with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            if user.is_verified:
                login_user(user)
                return redirect(url_for('home'))
            else:
                flash('Please verify your email before logging in.')
        else:
            flash('Invalid email or password.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already exists.')
        else:
            hashed_pw = generate_password_hash(password)
            new_user = User(username=username, email=email, phone=phone, password=hashed_pw)
            db.session.add(new_user)
            db.session.commit()
            code = generate_code()
            verification_codes[email] = code
            send_verification_code(email, code)
            session['email_to_verify'] = email
            return redirect(url_for('verify_email'))
    return render_template('register.html')

@app.route('/verify', methods=['GET', 'POST'])
def verify_email():
    email = session.get('email_to_verify')
    if not email:
        return redirect(url_for('register'))
    if request.method == 'POST':
        code = request.form['code']
        if code == verification_codes.get(email):
            user = User.query.filter_by(email=email).first()
            user.is_verified = True
            db.session.commit()
            flash('Email verified. Please login.')
            return redirect(url_for('login'))
        else:
            flash('Incorrect verification code.')
    return render_template('verify_email.html')

@app.route('/forgot-password')
def forgot_password():
    return render_template('forgot_password.html')

@app.route('/service/<service_type>')
@login_required
def service(service_type):
    providers = ServiceProvider.query.filter_by(service_type=service_type).all()
    return render_template('services.html', providers=providers, service=service_type)

@app.route('/book_services', methods=['POST'])
@login_required
def book_services():
    selected_services = request.form.getlist('services')
    preferred_date = request.form.get('date')
    preferred_time = request.form.get('time')
    if not selected_services:
        flash("Please select at least one service.")
        return redirect(url_for('home'))
    booking = Booking(user_id=current_user.id, services=', '.join(selected_services),
                      date=preferred_date, time=preferred_time)
    db.session.add(booking)
    db.session.commit()
    flash(f"Successfully booked: {', '.join(selected_services)} on {preferred_date} at {preferred_time}")
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
