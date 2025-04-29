from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from config import create_connection
from email_utils import generate_code, send_verification_code, send_reset_link
import threading
from datetime import datetime
from itsdangerous import URLSafeTimedSerializer
from flask import request, jsonify


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

        if user and check_password_hash(user['password'], password):
            if user['is_verified']:
                login_user(User(user['user_id'], user['name'], email, user['phone_number']))
                session['user_id'] = user['user_id']
                session['username'] = user['name']

                # 👇 Check if redirectAfterLogin is set
                if session.get('redirectAfterLogin') == 'checkout':
                    session.pop('redirectAfterLogin')  # Remove after use
                    return redirect(url_for('checkout'))

                flash("Login successful.")
                return redirect(url_for('home'))
            else:
                flash("Please verify your email first.")
        else:
            flash("Invalid email or password.")

    # Before showing login page, check if we came because of redirect
    if request.args.get('next') == 'checkout':
        session['redirectAfterLogin'] = 'checkout'

    return render_template('login.html')



@app.route('/history')
@login_required
def history():
    conn = create_connection()
    cur = conn.cursor(dictionary=True)

    # 1. Fetch all blocked slots for this user
    cur.execute("""
        SELECT bs.blocked_id, bs.date, bs.time_slot, p.place_name
        FROM blocked_slots bs
        JOIN Users u ON bs.user_id = u.user_id
        LEFT JOIN Employees e ON e.employee_id IN (
            SELECT employee_id FROM blocked_employee WHERE blocked_id = bs.blocked_id
        )
        LEFT JOIN places p ON e.place_id = p.place_id
        WHERE bs.user_id = %s
        ORDER BY bs.date DESC, bs.time_slot
    """, (current_user.id,))
    slots = cur.fetchall()

    history = []

    for slot in slots:
        # Get tasks for this slot
        cur.execute("SELECT task_name FROM blocked_task WHERE blocked_id = %s", (slot['blocked_id'],))
        tasks = [t['task_name'] for t in cur.fetchall()]

        # Get assigned employee
        cur.execute("""
            SELECT e.name FROM Employees e
            JOIN blocked_employee be ON e.employee_id = be.employee_id
            WHERE be.blocked_id = %s
            LIMIT 1
        """, (slot['blocked_id'],))
        employee = cur.fetchone()
        employee_name = employee['name'] if employee else "N/A"

        history.append({
            'date': slot['date'].strftime('%d-%m-%Y') if slot['date'] else "N/A",
            'time_slot': slot['time_slot'],
            'tasks': tasks,
            'employee_name': employee_name,
            'place': slot['place_name'] or "N/A"
        })


    cur.close()
    conn.close()

    return render_template("history.html", history=history)

verification_codes={}
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

from datetime import datetime

@app.route('/check-availability', methods=['POST'])
def check_availability():
    try:
        data = request.get_json()
        input_date = data.get('date')  # e.g., '25/04/2025'
        time_slot = data.get('time')
        cart_count = int(data.get('cart_count', 0))

        if not input_date or not time_slot or cart_count == 0:
            return jsonify({'status': 'error', 'message': 'Missing date, time, or cart items.'}), 400

        # 🔄 Convert 'DD/MM/YYYY' → 'YYYY-MM-DD'
        try:
            formatted_date = datetime.strptime(input_date, '%d/%m/%Y').strftime('%Y-%m-%d')
        except ValueError:
            return jsonify({'status': 'error', 'message': 'Invalid date format. Use DD/MM/YYYY.'}), 400

        # Determine the required number of employees
        if cart_count <= 4:
            min_required = 1
        elif cart_count <= 8:
            min_required = 2
        elif cart_count <= 12:
            min_required = 3
        else:
            return jsonify({'status': 'error', 'message': 'Too many cart items selected.'}), 400

        conn = create_connection()
        cursor = conn.cursor()

        # Step 1: Total employees
        cursor.execute("SELECT COUNT(*) FROM Employees")
        total_employees = cursor.fetchone()[0]

        # Step 2: Blocked employees for that date/time
        cursor.execute("""
            SELECT COUNT(DISTINCT be.employee_id)
            FROM blocked_employee AS be
            JOIN blocked_slots AS bs ON be.blocked_id = bs.blocked_id
            WHERE bs.date = %s AND bs.time_slot = %s
        """, (formatted_date, time_slot))
        blocked_employees = cursor.fetchone()[0]

        available_employees = total_employees - blocked_employees

        if available_employees >= min_required:
            return jsonify({'status': 'success', 'message': 'Enough employees are available for your selected slot.'})
        else:
            return jsonify({
                'status': 'fail',
                'message': f'Only {available_employees} employees available on {input_date} at {time_slot}. Required: {min_required}. Please select a new time slot.'
            })

    except Exception as e:
        print("Availability check error:", e)
        return jsonify({'status': 'error', 'message': 'Server error occurred. Please try again.'}), 500


@app.route("/check-out")
def checkout():
    return render_template("check-out.html")

@app.route('/confirmation')
def confirmation():
    return render_template('confirmation.html')

from flask import Flask, request, jsonify, session, redirect, url_for
from flask_login import current_user, login_required
import mysql.connector
from datetime import datetime


@app.route('/confirm-booking', methods=['POST'])
@login_required
def confirm_booking():
    try:
        data = request.get_json()
        payment_summary = data.get('paymentSummary')
        cart_items = data.get('cartItems')
        date = data.get('date')
        time = data.get('time')

        user_id = current_user.id  # Get the logged-in user's ID

        # Step 1: Insert into blocked_slots table
        conn = create_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO blocked_slots (user_id, date, time_slot)
            VALUES (%s, %s, %s)
        """, (user_id, date, time))
        conn.commit()

        # Get the inserted booked slot ID
        cursor.execute("SELECT LAST_INSERT_ID()")
        booked_id = cursor.fetchone()[0]

        # Step 2: Insert into blocked_tasks table for each cart item
        for item in cart_items:
            cursor.execute("""
                INSERT INTO blocked_task (blocked_id, task_name)
                VALUES (%s, %s)
            """, (booked_id, item['name']))

        # Step 3: Determine the minimum number of employees required
        cart_count = len(cart_items)
        if cart_count <= 4:
            min_required = 1
        elif cart_count <= 8:
            min_required = 2
        elif cart_count <= 12:
            min_required = 3
        else:
            return jsonify({'status': 'error', 'message': 'Too many cart items selected.'}), 400
        
        # Step 4: Retrieve available employees for the selected date and time
        formatted_date = datetime.strptime(date, '%d/%m/%Y').strftime('%Y-%m-%d')

        cursor.execute("""
            SELECT employee_id
            FROM Employees
            WHERE employee_id NOT IN (
                SELECT DISTINCT be.employee_id
                FROM blocked_employee AS be
                JOIN blocked_slots AS bs ON be.blocked_id = bs.blocked_id
                WHERE bs.date = %s AND bs.time_slot = %s
            )
        """, (formatted_date, time))

        available_employees = cursor.fetchall()

        if len(available_employees) < min_required:
            return jsonify({
                'status': 'error',
                'message': f'Not enough available employees for the selected slot. Available: {len(available_employees)}, Required: {min_required}.'
            }), 400

        # Step 5: Insert into blocked_employees table
        for i in range(min_required):
            cursor.execute("""
                INSERT INTO blocked_employee (blocked_id, employee_id)
                VALUES (%s, %s)
            """, (booked_id, available_employees[i][0]))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({'status': 'success', 'message': 'Booking confirmed successfully!'})

    except Exception as e:
        print(f"Error during booking: {e}")
        return jsonify({'status': 'error', 'message': 'Server error occurred. Please try again.'}), 500


if __name__ == '__main__':
    app.run(debug=True)