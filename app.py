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



@app.route('/history', methods=['GET', 'POST'])
@login_required
def history():
    conn = create_connection()
    cur = conn.cursor(dictionary=True)

    if request.method == 'POST':
        booking_id = request.form.get('booking_id')
        subservice = request.form.get('subservice')

        if booking_id and not subservice:
            # Cancel the entire booking
            cur.execute("UPDATE blocked_slots SET booking_status = 'cancelled' WHERE blocked_id = %s", (booking_id,))
            cur.execute("UPDATE blocked_employee SET booking_status = 'cancelled' WHERE blocked_id = %s", (booking_id,))
            cur.execute("UPDATE blocked_task SET booking_status = 'cancelled' WHERE blocked_id = %s", (booking_id,))
            conn.commit()
            flash('Booking cancelled successfully.')

        elif booking_id and subservice:
            # Cancel a specific subservice
            cur.execute("""
                UPDATE blocked_task 
                SET booking_status = 'cancelled'
                WHERE blocked_id = %s AND task_name = %s
            """, (booking_id, subservice))

            cur.execute("""
                SELECT be.employee_id, be.task_id 
                FROM blocked_employee be
                JOIN SubServices s ON s.task_id = be.task_id
                WHERE be.blocked_id = %s AND s.subservice_name = %s
            """, (booking_id, subservice))
            result = cur.fetchone()

            if result:
                emp_id = result['employee_id']
                task_id = result['task_id']

                # Check if any active tasks remain for the same employee & task_id
                cur.execute("""
                    SELECT COUNT(*) AS count
                    FROM blocked_task bt
                    JOIN SubServices s ON bt.task_name = s.subservice_name
                    WHERE bt.blocked_id = %s AND s.task_id = %s AND bt.booking_status != 'cancelled'
                """, (booking_id, task_id))
                task_count = cur.fetchone()['count']

                if task_count == 0:
                    # Cancel employee-task assignment too
                    cur.execute("""
                        UPDATE blocked_employee 
                        SET booking_status = 'cancelled' 
                        WHERE blocked_id = %s AND employee_id = %s
                    """, (booking_id, emp_id))

            conn.commit()
            flash('Subservice cancelled successfully.')

        return redirect(url_for('history'))

    # --- GET: Render history ---
    cur.execute("""
        SELECT bs.blocked_id, bs.date, bs.time_slot, bs.booking_status
        FROM blocked_slots bs
        WHERE bs.user_id = %s
        ORDER BY 1 DESC, bs.time_slot
    """, (current_user.id,))
    slots = cur.fetchall()

    history = []

    for slot in slots:
        cur.execute("""
            SELECT e.name AS employee_name, bt.task_name AS subservice_name, bt.booking_status
            FROM blocked_employee be
            JOIN Employees e ON be.employee_id = e.employee_id
            JOIN blocked_task bt ON bt.blocked_id = be.blocked_id
            WHERE be.blocked_id = %s
              AND bt.task_name IN (
                  SELECT s.subservice_name FROM SubServices s WHERE s.task_id = be.task_id
              )
        """, (slot['blocked_id'],))
        mappings = cur.fetchall()

        employee_tasks = {}
        for row in mappings:
            emp_name = row['employee_name']
            subservice = row['subservice_name']
            sub_status = row['booking_status']
            if emp_name not in employee_tasks:
                employee_tasks[emp_name] = []
            employee_tasks[emp_name].append((subservice, sub_status))

        history.append({
            'id': slot['blocked_id'],
            'date': slot['date'].strftime('%d-%m-%Y') if slot['date'] else "N/A",
            'time_slot': slot['time_slot'],
            'employee_tasks': employee_tasks,
            'status': slot['booking_status'],
        })

    cur.close()
    conn.close()
    return render_template("history.html", history=history)

verification_codes = {}
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
            formatted_date = datetime.strptime(input_date, '%d/%m/%Y').date()
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
        subservice_to_task = {
            # AC services
            "AC General Service": 1,
            "AC Gas Refill": 1,
            "AC Installation/Uninstallation": 1,
            "AC Not Cooling Issue Fix": 1,
            # Floor services
            "Deep Floor Scrubbing": 2,
            "Stain Removal Treatment": 2,
            "Carpet/Mat Cleaning": 2,
            "Polishing & Buffing": 2,
            # Kitchen services
            "Full Kitchen Deep Clean": 3,
            "Grease Removal (Chimney/Stove)": 3,
            "Cabinet Cleaning": 3,
            "Sink & Drain Cleaning": 3
        }

        data = request.get_json()
        cart_items = data.get('cartItems')
        date = datetime.strptime(data.get('date'), "%d/%m/%Y").date()
        time = data.get('time')
        user_id = current_user.id

        conn = create_connection()
        cursor = conn.cursor()

        # Step 1: Block the slot
        cursor.execute("""
            INSERT INTO blocked_slots (user_id, date, time_slot)
            VALUES (%s, %s, %s)
        """, (user_id, date, time))
        conn.commit()

        cursor.execute("SELECT LAST_INSERT_ID()")
        booked_id = cursor.fetchone()[0]

        # Step 2: Insert blocked tasks and track task IDs
        task_ids_set = set()
        for item in cart_items:
            task_name = item['name']
            task_id = subservice_to_task.get(task_name)
            if not task_id:
                return jsonify({'status': 'error', 'message': f"Unknown sub-service: {task_name}"}), 400

            cursor.execute("""
                INSERT INTO blocked_task (blocked_id, task_name)
                VALUES (%s, %s)
            """, (booked_id, task_name))

            task_ids_set.add(task_id)

        assigned_employees = []

        # Step 3: For each task_id, find available specialized employee
        for task_id in task_ids_set:
            # Get already assigned employee IDs
            already_assigned_ids = [emp_id for emp_id, _ in assigned_employees]
            in_clause = ', '.join(['%s'] * len(already_assigned_ids)) if already_assigned_ids else None

            if in_clause:
                query = f"""
                    SELECT e.employee_id
                    FROM Employees AS e
                    JOIN Employee_Specializations es ON e.employee_id = es.employee_id
                    WHERE es.task_id = %s
                      AND e.employee_id NOT IN (
                          SELECT be.employee_id
                          FROM blocked_employee AS be
                          JOIN blocked_slots AS bs ON be.blocked_id = bs.blocked_id
                          WHERE bs.date = %s AND bs.time_slot = %s
                      )
                      AND e.employee_id NOT IN ({in_clause})
                    LIMIT 1
                """
                params = [task_id, date, time] + already_assigned_ids
            else:
                query = """
                    SELECT e.employee_id
                    FROM Employees AS e
                    JOIN Employee_Specializations es ON e.employee_id = es.employee_id
                    WHERE es.task_id = %s
                      AND e.employee_id NOT IN (
                          SELECT be.employee_id
                          FROM blocked_employee AS be
                          JOIN blocked_slots AS bs ON be.blocked_id = bs.blocked_id
                          WHERE bs.date = %s AND bs.time_slot = %s
                      )
                    LIMIT 1
                """
                params = [task_id, date, time]

            cursor.execute(query, params)
            result = cursor.fetchone()
            if result:
                assigned_employees.append((result[0], task_id))
            else:
                return jsonify({
                    'status': 'error',
                    'message': f'No available specialized employee for task ID {task_id} at {time} on {date}.'
                }), 400

        # Step 4: Insert into blocked_employee with task_id
        for emp_id, task_id in assigned_employees:
            cursor.execute("""
                INSERT INTO blocked_employee (blocked_id, employee_id, task_id)
                VALUES (%s, %s, %s)
            """, (booked_id, emp_id, task_id))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({'status': 'success', 'message': 'Booking confirmed successfully!'})

    except Exception as e:
        print(f"Error during booking: {e}")
        return jsonify({'status': 'error', 'message': 'Server error occurred. Please try again.'}), 500

if __name__ == '__main__':
    app.run(debug=True)