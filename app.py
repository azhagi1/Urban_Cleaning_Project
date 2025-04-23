from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from config import create_connection
from email_utils import generate_code, send_verification_code
from datetime import datetime, timedelta
import threading
import mysql.connector

from flask import Flask
from config import create_connection, SECRET_KEY

app = Flask(__name__)
app.secret_key = SECRET_KEY  # Flask session key


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
        print(user)
        if user and (user['password']==password):
            if user['is_verified']:
                login_user(User(user['user_id'], user['name'], email, user['phone_number']))
                return redirect(url_for('home'))
            else:
                flash("Please verify your email.")
        else:
            flash("Invalid credentials.")
        flash("Login successful.") 
    return render_template('home.html')

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


@app.route('/forgot-password')
def forgot_password():
    return render_template('forgot_password.html')

from flask import jsonify

@app.route('/book_services', methods=['POST'])
def book_services():
    if request.method == 'POST':
        selected_date = request.form.get('date')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        selected_tasks = request.form.getlist('services')

        if not selected_tasks:
            flash("Please select at least one service.")
            return redirect(url_for('home'))

        start_datetime = f"{selected_date} {start_time}:00"
        end_datetime = f"{selected_date} {end_time}:00"

        conn = create_connection()
        cursor = conn.cursor(dictionary=True)

        # Step 1: Get task IDs for selected task names
        format_strings = ','.join(['%s'] * len(selected_tasks))
        cursor.execute(f"SELECT task_id FROM Tasks WHERE task_name IN ({format_strings})", tuple(selected_tasks))
        task_ids = [row['task_id'] for row in cursor.fetchall()]

        if not task_ids:
            flash("No matching tasks found.")
            return redirect(url_for('home'))

        # Step 2: Find employees who have ALL the selected specializations
        cursor.execute(f"""
            SELECT employee_id
            FROM Employee_Specializations
            WHERE task_id IN ({','.join(['%s'] * len(task_ids))})
            GROUP BY employee_id
            HAVING COUNT(DISTINCT task_id) = %s
        """, (*task_ids, len(task_ids)))

        employee_ids = [row['employee_id'] for row in cursor.fetchall()]

        if not employee_ids:
            flash("No employee found with all selected skills.")
            return redirect(url_for('home'))

        # Step 3: Filter out blocked employees in the time window
        cursor.execute(f"""
            SELECT DISTINCT employee_id
            FROM Employee_Blocked_Slots
            WHERE block_status = 'confirmed'
              AND (
                    (blocked_from <= %s AND blocked_to > %s) OR
                    (blocked_from < %s AND blocked_to >= %s) OR
                    (blocked_from >= %s AND blocked_to <= %s)
                  )
        """, (start_datetime, start_datetime, end_datetime, end_datetime, start_datetime, end_datetime))

        blocked_ids = [row['employee_id'] for row in cursor.fetchall()]
        available_ids = [emp_id for emp_id in employee_ids if emp_id not in blocked_ids]

        # Step 4: Get employee details
        if available_ids:
            format_strings = ','.join(['%s'] * len(available_ids))
            cursor.execute(f"SELECT * FROM Employees WHERE employee_id IN ({format_strings})", tuple(available_ids))
            available_employees = cursor.fetchall()
        else:
            available_employees = []

        cursor.close()
        conn.close()

        return render_template('available_employees.html', employees=available_employees, tasks=selected_tasks)

if __name__ == '__main__':
    app.run(debug=True)
