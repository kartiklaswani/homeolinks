from flask import Flask, render_template, request, jsonify, redirect, session
from datetime import datetime
import psycopg2
from urllib.parse import urlparse
import os

app = Flask(__name__)
app.secret_key = "homeolinks_secret_key"

# ---------------- DATABASE CONNECTION ----------------
DATABASE_URL = os.environ.get("DATABASE_URL")


def get_db_connection():

    result = urlparse(DATABASE_URL)

    conn = psycopg2.connect(
        dbname=result.path[1:],
        user=result.username,
        password=result.password,
        host=result.hostname,
        port=result.port
    )

    return conn

# ---------------- DATABASE ----------------
def init_db():

    conn = get_db_connection()
    c = conn.cursor()

    # appointments table
    c.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id SERIAL PRIMARY KEY,
            name TEXT,
            phone TEXT,
            date TEXT,
            time TEXT,
            message TEXT
        )
    ''')

    # patients table
    c.execute('''
        CREATE TABLE IF NOT EXISTS patients (
            id SERIAL PRIMARY KEY,
            name TEXT,
            age TEXT,
            gender TEXT,
            phone TEXT,
            case_details TEXT,
            created_at TEXT,
            status TEXT DEFAULT 'active'
        )
    ''')

    # followups table
    c.execute('''
        CREATE TABLE IF NOT EXISTS followups (
            id SERIAL PRIMARY KEY,
            patient_id INTEGER,
            datetime TEXT,
            notes TEXT,
            prescription TEXT
        )
    ''')

    conn.commit()
    conn.close()


init_db()

# ---------------- WEBSITE ----------------
@app.route('/')
def home():
    return render_template('home.html')


@app.route('/services')
def services():
    return render_template('services.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/contact')
def contact():
    return render_template('contact.html')


@app.route('/faq')
def faq():
    return render_template('faq.html')


@app.route('/testimonials')
def testimonials():
    return render_template('testimonials.html')


@app.route('/blog/<post>')
def blog(post):
    return render_template(post + ".html")


# ---------------- BOOK APPOINTMENT ----------------
@app.route('/book', methods=['GET', 'POST'])
def book():

    if request.method == 'POST':

        name = request.form['name']
        phone = request.form['phone']
        date = request.form['date']
        time = request.form['time']
        message = request.form['message']

        today = datetime.now().strftime("%Y-%m-%d")
        now = datetime.now().strftime("%H:%M")

        # prevent past booking
        if date < today:
            return "Cannot book past date"
        
        # Block Sundays
        selected_day = datetime.strptime(date, "%Y-%m-%d").weekday()

        # Sunday = 6
        if selected_day == 6:
            return "Clinic remains closed on Sundays"

        if date == today and time <= now:
            return "Cannot book past time"
            

        conn = get_db_connection()
        c = conn.cursor()

        # CHECK IF SLOT ALREADY BOOKED
        c.execute(
            "SELECT * FROM appointments WHERE date=%s AND time=%s",
            (date, time)
        )

        existing_appointment = c.fetchone()

        if existing_appointment:
            conn.close()

            return """
            <h2 style='color:red; text-align:center; margin-top:50px;'>
            Sorry, this appointment slot is already booked.
            Please choose another time.
            </h2>
            """

        # SAVE NEW APPOINTMENT
        c.execute(
            """
            INSERT INTO appointments
            (name, phone, date, time, message)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (name, phone, date, time, message)
        )

        conn.commit()
        conn.close()

        return render_template(
            "confirmation.html",
            name=name,
            phone=phone,
            date=date,
            time=time
        )

    return render_template('book.html')


# ---------------- TIME SLOTS ----------------
@app.route('/get_slots', methods=['POST'])
def get_slots():

    data = request.get_json()
    date = data['date']

    slots = []

    # Morning slots
    for h in range(10, 13):
        slots.append(f"{h:02d}:00")
        slots.append(f"{h:02d}:30")

    # Evening slots
    slots.append("17:30")

    for h in range(18, 20):
        slots.append(f"{h:02d}:00")
        slots.append(f"{h:02d}:30")

    # Last slot
    slots.append("20:00")

    conn = get_db_connection()
    c = conn.cursor()

    c.execute(
        "SELECT time FROM appointments WHERE date=%s",
        (date,)
    )

    booked = [x[0] for x in c.fetchall()]

    conn.close()

    available = [s for s in slots if s not in booked]

    return jsonify(available)


# ---------------- ADMIN LOGIN ----------------
@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        if username == "admin" and password == "homeolinks123":

            session['admin_logged_in'] = True
            return redirect('/admin')

        return """
        <h2 style='color:red; text-align:center; margin-top:50px;'>
        Invalid username or password
        </h2>
        """

    return render_template('login.html')


# ---------------- ADMIN DASHBOARD ----------------
@app.route('/admin')
def admin():

    if not session.get('admin_logged_in'):
        return redirect('/admin-login')

    conn = get_db_connection()
    c = conn.cursor()

    c.execute("""
        SELECT * FROM appointments
        ORDER BY date ASC, time ASC
    """)

    appointments = c.fetchall()

    conn.close()

    return render_template(
        'admin.html',
        appointments=appointments
    )


# ---------------- DELETE APPOINTMENT ----------------
@app.route('/delete_appointment/<int:id>')
def delete_appointment(id):

    conn = get_db_connection()
    c = conn.cursor()

    # Get appointment details BEFORE deleting
    c.execute(
        "SELECT name, phone, date, time FROM appointments WHERE id=%s",
        (id,)
    )

    appointment = c.fetchone()

    if not appointment:
        conn.close()
        return redirect('/admin')

    name = appointment[0]
    phone = appointment[1]
    date = appointment[2]
    time = appointment[3]

    # Delete appointment
    c.execute(
        "DELETE FROM appointments WHERE id=%s",
        (id,)
    )

    conn.commit()
    conn.close()

    # WhatsApp message
    message = f'''
Dear {name},

Your appointment at Homeolinks Clinic scheduled for:

Date: {date}
Time: {time}

has been cancelled, due to unavoidable circumstances.

Please contact clinic for rescheduling, or book another slot.

Homeolinks Clinic
'''

    # Remove spaces/special characters
    import urllib.parse

    encoded_message = urllib.parse.quote(message)

    # Open WhatsApp
    whatsapp_url = f"https://wa.me/91{phone}?text={encoded_message}"

    return redirect(whatsapp_url)


# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():

    session.pop('admin_logged_in', None)
    return redirect('/')

# ---------------- DELETE PATIENT ----------------
@app.route('/delete_patient/<int:id>')
def delete_patient(id):

    conn = get_db_connection()
    c = conn.cursor()

    # Get patient details first
    c.execute(
        "SELECT name, phone FROM patients WHERE id=%s",
        (id,)
    )

    patient = c.fetchone()

    if not patient:
        conn.close()
        return redirect('/admin')

    name = patient[0]
    phone = patient[1]

    # Soft delete patient
    c.execute(
        "UPDATE patients SET status='deleted' WHERE id=%s",
        (id,)
    )

    conn.commit()
    conn.close()

    # WhatsApp message
    message = f'''
Dear {name},

Your patient profile at Homeolinks Clinic has been marked inactive/deleted from our active records.

If this was done by mistake or you wish to continue treatment, kindly contact the clinic.

Homeolinks Clinic
'''

    import urllib.parse

    encoded_message = urllib.parse.quote(message)

    whatsapp_url = f"https://wa.me/91{phone}?text={encoded_message}"

    return redirect(whatsapp_url)

# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)