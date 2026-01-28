import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, g 

app = Flask(__name__)
DATABASE = 'demo.db'

# Database connection
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

# Close database connection
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# Log login attempts
def log_attempt(method, username, status, query_executed):
    db = get_db()
    cursor = db.cursor()
    timestamp = datetime.now().strftime("%H:%M:%S")
    cursor.execute("""
        INSERT INTO audit_log (timestamp, method, username, status, query_snippet)
        VALUES (?, ?, ?, ?, ?)
    """, (timestamp, method, username, status, query_executed))
    db.commit()

# Retrieve last 10 logs
def get_logs():
    """Fetching the last 10 logs"""
    db = get_db()
    cursor = db.cursor()
    # We check if the table exists in case the user runs for the first time
    try:
        cursor.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 10")
        return cursor.fetchall()
    except:
        return []

# Initialize the database
def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        # Users table
        cursor.execute("DROP TABLE IF EXISTS users")
        cursor.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                password TEXT NOT NULL
            )
        """)
        
        # --- Audit Log Table ---
        cursor.execute("DROP TABLE IF EXISTS audit_log")
        cursor.execute("""
            CREATE TABLE audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                method TEXT,
                username TEXT,
                status TEXT,
                query_snippet TEXT
            )
        """)

        users = [('admin', 'secret123'), ('alice', 'wonderland'), ('bob', 'builder')]
        cursor.executemany("INSERT INTO users (username, password) VALUES (?, ?)", users)
        db.commit()

# Routes
@app.route('/reset')
def reset_db():
    init_db()
    return render_template('index.html', v_result="🔄 System Reset!", v_status="success", history=[])

@app.route('/login_vulnerable', methods=['POST'])
def login_vulnerable():
    username = request.form['username']
    password = request.form['password']
    
    db = get_db()
    cursor = db.cursor()
    query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"
    
    try:
        cursor.execute(query)
        user = cursor.fetchone()
        
        if user:
            # Logging success
            log_attempt("VULNERABLE", username, "SUCCESS", query)
            return render_template('index.html', v_result="✅ Logged in as: " + user['username'], v_query=query, v_status="success", history=get_logs())
        else:
            # Logging failure
            log_attempt("VULNERABLE", username, "FAILED", query)
            return render_template('index.html', v_result="❌ Login Failed", v_query=query, v_status="fail", history=get_logs())
            
    except Exception as e:
        log_attempt("VULNERABLE", username, "ERROR", str(e))
        return render_template('index.html', v_result=f"💥 Error: {e}", v_query=query, v_status="error", history=get_logs())

@app.route('/login_secure', methods=['POST'])
def login_secure():
    username = request.form['username']
    password = request.form['password']
    
    db = get_db()
    cursor = db.cursor()
    query_structure = "SELECT * FROM users WHERE username = ? AND password = ?"
    
    cursor.execute(query_structure, (username, password))
    user = cursor.fetchone()
    display_query = f"Prepared Statement: ('{username}', '{password}')"

    if user:
        log_attempt("SECURE", username, "SUCCESS", "Parameterized Query")
        return render_template('index.html', s_result="✅ Logged in as: " + user['username'], s_query=display_query, s_status="success", history=get_logs())
    else:
        log_attempt("SECURE", username, "BLOCKED", "Parameterized Query")
        return render_template('index.html', s_result="❌ Attack Blocked", s_query=display_query, s_status="fail", history=get_logs())

@app.route('/')
def home():
    # On initial load - display empty or existing history
    return render_template('index.html', history=get_logs())

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)