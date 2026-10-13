import sqlite3
from flask import Flask, render_template, request, redirect, url_for,abort

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
@app.route("/delete/<int:note_id>", methods=["POST"])
def delete(note_id):
    with get_db() as conn:
        conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    return redirect(url_for("home"))

@app.route("/edit/<int:note_id>", methods=["GET", "POST"])
def edit(note_id):
    with get_db() as conn:
        note = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        if note is None:
            abort(404)
        if request.method == "POST":
            conn.execute(
                "UPDATE notes SET subject = ?, title = ?, content = ? WHERE id = ?",
                (request.form["subject"], request.form["title"], request.form["content"], note_id),
            )
            return redirect(url_for("home"))
    return render_template("edit.html", note=note)
if __name__ == "__main__":
    init_db()
    app.run(debug=True)