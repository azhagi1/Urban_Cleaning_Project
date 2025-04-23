from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from config import create_connection
from email_utils import generate_code, send_verification_code
import mysql.connector

from flask import Flask
from config import create_connection, SECRET_KEY

app = Flask(__name__)
app.secret_key = SECRET_KEY  # Flask session key


login_manager = LoginManager(app)
login_manager.login_view = 'login'

verification_codes = {}

class User(UserMixin):
    def __init__(self, id, username, email, phone):
        self.id = id
        self.username = username
        self.email = email
        self.phone = phone

@login_manager.user_loader
def load_user(user_id):
    conn = create_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Users WHERE user_id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if user:
        return User(user['user_id'], user['name'], user['email'], user['phone_number'])
    return None

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        """if user and check_password_hash(user['password'], password):
            if user['is_verified']:
                login_user(User(user['user_id'], user['name'], email, user['phone_number']))
                return redirect(url_for('home'))
            else:
                flash("Please verify your email.")
        else:
            flash("Invalid credentials.")"""
        flash("Login successful.") 
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['username']
        email = request.form['email']
        phone = request.form['phone']
        password = generate_password_hash(request.form['password'])

        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Users WHERE email = %s", (email,))
        if cursor.fetchone():
            flash("Email already exists.")
            cursor.close()
            conn.close()
            return redirect(url_for('register'))

        cursor.execute("INSERT INTO Users (name, email, phone_number, password) VALUES (%s, %s, %s, %s)",
                       (name, email, phone, password))
        conn.commit()
        cursor.close()
        conn.close()

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
            conn = create_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE Users SET is_verified = TRUE WHERE email = %s", (email,))
            conn.commit()
            cursor.close()
            conn.close()
            flash("Email verified. Please login.")
            return redirect(url_for('login'))
        else:
            flash("Incorrect code.")
    return render_template('verify_email.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/book_services', methods=['POST'])
@login_required
def book_services():
    services = ', '.join(request.form.getlist('services'))
    date = request.form['date']
    time = f"{request.form['start_time']} - {request.form['end_time']}"

    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO Booking (user_id, services, date, time) VALUES (%s, %s, %s, %s)",
                   (current_user.id, services, date, time))
    conn.commit()
    cursor.close()
    conn.close()

    flash(f"Booked: {services} on {date} at {time}")
    return redirect(url_for('home'))

@app.route('/forgot-password')
def forgot_password():
    return render_template('forgot_password.html')

if __name__ == '__main__':
    app.run(debug=True)
