from flask import Flask, render_template, request, jsonify, redirect, session
from datetime import datetime
import psycopg2
from urllib.parse import urlparse
import os
import json
import gspread
from google.oauth2.service_account import Credentials
import requests

# ---------------- GOOGLE SHEETS ----------------

try:
    SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
    ]

    credentials_info = json.loads(
        os.environ["GOOGLE_CREDENTIALS"]
    )

    creds = Credentials.from_service_account_info(
        credentials_info,
        scopes=SCOPES
    )

    client = gspread.authorize(creds)

    sheet = client.open("Homeolinks Appointments").sheet1

except Exception as e:
    sheet = str(e)

TELEGRAM_BOT_TOKEN = "8931605522:AAGamxwdmBX9g8_XPSYXTOcFXVoHcHx8no4"

TELEGRAM_CHAT_ID = "8942704437"

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


try:
    init_db()
except:
    print("Database unavailable - starting without database")

# ---------------- WEBSITE ----------------
@app.route('/test-sheet')
def test_sheet():

    if isinstance(sheet, str):
        return f"Google Sheets startup error: {sheet}"

    if sheet is None:
        return "Google Sheets not connected"

    records = sheet.get_all_values()

    return f"Connected successfully. Rows found: {len(records)}"

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

        telegram_message = f"""
        📢 New Appointment Booking

        👤 Name: {name}

        📞 Phone: {phone}

        📅 Date: {date}

        ⏰ Time: {time}

        📝 Message: {message}

        — Homeolinks Website
        """

        telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

        requests.post(
            telegram_url,
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": telegram_message
            }
        )

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

        # SAVE TO GOOGLE SHEETS

        sheet.append_row([
            date,
            time,
            name,
            phone,
            message
        ])    

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

    # READ BOOKINGS FROM GOOGLE SHEETS

    records = sheet.get_all_values()

    booked = []

    for row in records[1:]:  # skip header row

        if len(row) >= 2:

            booked_date = row[0]
            booked_time = row[1]

            if booked_date == date:
                booked.append(booked_time)

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

    records = sheet.get_all_values()

    appointments = []

    # Skip header row
    for row_number, row in enumerate(records[1:], start=2):

        if len(row) >= 5:

            appointments.append({
                "row_number": row_number,
                "date": row[0],
                "time": row[1],
                "name": row[2],
                "phone": row[3],
                "message": row[4]
            })

    # Sort appointments by date and time
    appointments.sort(
        key=lambda x: (x["date"], x["time"])
    )

    return render_template(
        'admin.html',
        appointments=appointments
    )

# ---------------- DELETE APPOINTMENT ----------------
@app.route('/delete_appointment/<int:row_number>')
def delete_appointment(row_number):

    records = sheet.get_all_values()

    # Make sure the requested row actually exists
    if row_number < 2 or row_number > len(records):
        return redirect('/admin')

    # Get appointment details before deleting
    appointment = records[row_number - 1]

    date = appointment[0]
    time = appointment[1]
    name = appointment[2]
    phone = appointment[3]

    # Delete the appointment from Google Sheets
    sheet.delete_rows(row_number)

    # WhatsApp cancellation message
    message = f'''
Dear {name},

We are sorry to inform you that your appointment at Homeolinks Clinic scheduled for:

Date: {date}
Time: {time}

has been cancelled, due to unavoidable circumstances.

Please contact clinic for rescheduling, or book another slot. Sorry for the inconvenience caused.

Homeolinks Clinic
'''

    import urllib.parse

    encoded_message = urllib.parse.quote(message)

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

@app.route('/robots.txt')
def robots():
    return """
User-agent: *
Allow: /

Sitemap: https://www.homeolinks.in/sitemap.xml
""", 200, {'Content-Type': 'text/plain'}


@app.route('/sitemap.xml')
def sitemap():

    sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>

<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">

<url>
<loc>https://www.homeolinks.in/</loc>
</url>

<url>
<loc>https://www.homeolinks.in/about</loc>
</url>

<url>
<loc>https://www.homeolinks.in/services</loc>
</url>

<url>
<loc>https://www.homeolinks.in/contact</loc>
</url>

<url>
<loc>https://www.homeolinks.in/faq</loc>
</url>

<url>
<loc>https://www.homeolinks.in/testimonials</loc>
</url>

<url>
<loc>https://www.homeolinks.in/book</loc>
</url>

<url>
<loc>https://www.homeolinks.in/blog/acne-blog</loc>
</url>

<url>
<loc>https://www.homeolinks.in/blog/allergy-blog</loc>
</url>

<url>
<loc>https://www.homeolinks.in/blog/arthritis-blog</loc>
</url>

<url>
<loc>https://www.homeolinks.in/blog/pcos-blog</loc>
</url>

<url>
<loc>https://www.homeolinks.in/blog/acidity-blog</loc>
</url>

<url>
<loc>https://www.homeolinks.in/blog/anxiety-blog</loc>
</url>

<url>
<loc>https://www.homeolinks.in/blog/children-blog</loc>
</url>

<url>
<loc>https://www.homeolinks.in/blog/thyroid-blog</loc>
</url>

<url>
<loc>https://www.homeolinks.in/blog/hairfall-blog</loc>
</url>

<url>
<loc>https://www.homeolinks.in/blog/eczema-blog</loc>
</url>

<url>
<loc>https://www.homeolinks.in/blog/asthma-blog</loc>
</url>

<url>
<loc>https://www.homeolinks.in/blog/periods-blog</loc>
</url>

</urlset>
"""

    response = app.response_class(
        sitemap_xml,
        mimetype='application/xml'
    )

    return response
@app.route('/google21c533c900d305ee.html')
def google_verify():
    return render_template('google21c533c900d305ee.html')    
# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)