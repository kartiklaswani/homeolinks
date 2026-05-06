from flask import Flask, render_template, request, jsonify, redirect
from datetime import datetime
import sqlite3

app = Flask(__name__)

# ---------------- DATABASE ----------------
def init_db():

    conn = sqlite3.connect('appointments.db')
    c = conn.cursor()

    # appointments
    c.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT,
            date TEXT,
            time TEXT,
            message TEXT
        )
    ''')

    # patients
    c.execute('''
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            age TEXT,
            gender TEXT,
            phone TEXT,
            case_details TEXT,
            created_at TEXT
        )
    ''')

    # safely add status column
    try:
        c.execute("ALTER TABLE patients ADD COLUMN status TEXT DEFAULT 'active'")
    except:
        pass

    # followups
    c.execute('''
        CREATE TABLE IF NOT EXISTS followups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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

        if date == today and time <= now:
            return "Cannot book past time"

        conn = sqlite3.connect('appointments.db')
        c = conn.cursor()

        c.execute(
            "INSERT INTO appointments VALUES(NULL,?,?,?,?,?)",
            (name, phone, date, time, message)
        )

        conn.commit()
        conn.close()

        return render_template(
            'confirmation.html',
            name=name,
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

    conn = sqlite3.connect('appointments.db')
    c = conn.cursor()

    c.execute(
        "SELECT time FROM appointments WHERE date=?",
        (date,)
    )

    booked = [x[0] for x in c.fetchall()]

    conn.close()

    available = [s for s in slots if s not in booked]

    return jsonify(available)




# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(debug=True)