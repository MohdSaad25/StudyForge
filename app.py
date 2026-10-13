import sqlite3
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)
DB = "studyforge.db"

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        subject = request.form["subject"]
        title = request.form["title"]
        content = request.form["content"]
        with get_db() as conn:
            conn.execute(
                "INSERT INTO notes (subject, title, content) VALUES (?, ?, ?)",
                (subject, title, content),
            )
        return redirect(url_for("home"))

    with get_db() as conn:
        notes = conn.execute("SELECT * FROM notes ORDER BY created_at DESC").fetchall()
    return render_template("index.html", notes=notes)

if __name__ == "__main__":
    init_db()
    app.run(debug=True)