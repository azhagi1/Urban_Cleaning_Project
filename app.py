from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from config import create_connection
from email_utils import generate_code, send_verification_code, send_reset_link
import threading
from datetime import datetime
from itsdangerous import URLSafeTimedSerializer



def generate_reset_token(email):
    return serializer.dumps(email, salt='password-reset-salt')

def verify_reset_token(token, expiration=3600):
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=expiration)
    except:
        return None
    return email


import mysql.connector

from flask import Flask
from config import create_connection, SECRET_KEY

app = Flask(__name__)
app.secret_key = SECRET_KEY  # Flask session key
serializer = URLSafeTimedSerializer(app.secret_key)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

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

def send_email_in_background(email, code):
    threading.Thread(target=send_verification_code, args=(email, code)).start()

from datetime import date

def get_places():
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT place_name FROM places")
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return [row[0] for row in results]

@app.route('/')
def home():
    places = get_places()
    today = date.today().strftime('%Y-%m-%d')
    return render_template('home.html',places=places, today=today)


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
        print(user)
        if user and check_password_hash(user['password'], password):
        
            if user['is_verified']:
                login_user(User(user['user_id'], user['name'], email, user['phone_number']))
                flash("Login successful.")
                return redirect(url_for('home'))
            else:
                flash("Please verify your email.")
        else:
            flash("Invalid credentials.")
        flash("Login successful.") 
    return render_template('login.html')

verification_codes = {}  # Format: { email: {"code": ..., "expires_at": ...} }

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        phone = request.form['phone']

        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Users WHERE email = %s", (email,))
        if cursor.fetchone():
            flash("Email already exists.")
            cursor.close()
            conn.close()
            return redirect(url_for('register'))

        cursor.execute("INSERT INTO Users (name, email, phone_number, is_verified) VALUES (%s, %s, %s, %s)",
                       (username, email, phone, False))
        conn.commit()
        cursor.close()
        conn.close()

        code = generate_code()
        verification_codes[email] = code
        send_email_in_background(email, code)  # ✅ send in background
        session['email_to_verify'] = email
        flash("Verification code sent to your email.")
        return redirect(url_for('verify_email'))
    return render_template('register.html')

@app.route('/verify', methods=['GET', 'POST'])
def verify_email():
    email = session.get('email_to_verify')
    if not email:
        return redirect(url_for('register'))

    if request.method == 'POST':
        if 'resend' in request.form:
            code = generate_code()
            verification_codes[email] = code
            send_email_in_background(email, code)  # ✅ resend in background
            flash("New verification code sent.")
        else:
            code = request.form['code']
            if code == verification_codes.get(email):
                flash("OTP verified. Please set your password.")
                return redirect(url_for('set_password'))
            else:
                flash("Incorrect verification code.")
    return render_template('verify_email.html', email=email)

# ---------- Set Password ----------
@app.route('/set-password', methods=['GET', 'POST'])
def set_password():
    email = session.get('email_to_verify')
    if not email:
        return redirect(url_for('register'))

    if request.method == 'POST':
        password = generate_password_hash(request.form['password'])
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE Users SET password = %s, is_verified = TRUE WHERE email = %s", (password, email))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Registration complete. You can now login.")
        session.pop('email_to_verify', None)
        return redirect(url_for('login'))
    return render_template('set_password.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.")
    return redirect(url_for('home'))

reset_codes = {}
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user:
            flash("Email not found.")
            return redirect(url_for('forgot_password'))

        token = generate_reset_token(email)
        reset_link = url_for('reset_password', token=token, _external=True)
        send_reset_link(email, reset_link)

        flash("Password reset link sent to your email.")
        return redirect(url_for('login'))

    return render_template('forgot_password.html')

def send_email_thread(email, code):
    threading.Thread(target=send_verification_code, args=(email, code)).start()


@app.route('/verify-reset', methods=['GET', 'POST'])
def verify_reset():
    email = session.get('reset_email')
    if not email:
        flash("Session expired.")
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        code_entered = request.form['code']
        if code_entered == reset_codes.get(email):
            flash("OTP verified.")
            return redirect(url_for('reset_password'))
        else:
            flash("Invalid code.")

    return render_template('verify_reset.html')
@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    email = verify_reset_token(token)
    if not email:
        flash("The reset link is invalid or has expired.")
        return redirect(url_for('login'))

    if request.method == 'POST':
        password = request.form['password']
        confirm = request.form['confirm_password']

        if password != confirm:
            flash("Passwords do not match.")
            return redirect(request.url)

        hashed = generate_password_hash(password)

        conn = create_connection()
        cursor = conn.cursor()

        # ✅ Update password and mark user as verified
        cursor.execute("""
            UPDATE Users 
            SET password = %s, is_verified = 1 
            WHERE email = %s
        """, (hashed, email))

        conn.commit()
        cursor.close()
        conn.close()

        flash("Password reset successful. Please login.")
        return redirect(url_for('login'))

    return render_template('reset_password_token.html', email=email)

@app.route("/check-out")
def checkout():
    return render_template("check-out.html")

@app.route('/confirmation')
def confirmation():
    return render_template('confirmation.html')

if __name__ == '__main__':
    app.run(debug=True)
