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
            CREATE TABLE IF NOT EXISTS flashcards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                note_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                ease REAL DEFAULT 2.5,
                interval_days INTEGER DEFAULT 0,
                repetitions INTEGER DEFAULT 0,
                next_review TEXT DEFAULT CURRENT_DATE
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

    selected = request.args.get("subject", "")
    with get_db() as conn:
        subjects = [r["subject"] for r in conn.execute(
            "SELECT DISTINCT subject FROM notes ORDER BY subject"
        ).fetchall()]
        if selected:
            notes = conn.execute(
                "SELECT * FROM notes WHERE subject = ? ORDER BY created_at DESC",
                (selected,),
            ).fetchall()
        else:
            notes = conn.execute("SELECT * FROM notes ORDER BY created_at DESC").fetchall()
    return render_template("index.html", notes=notes, subjects=subjects, selected=selected)
@app.route("/delete/<int:note_id>", methods=["POST"])
def delete(note_id):
    with get_db() as conn:
        conn.execute("DELETE FROM flashcards WHERE note_id = ?", (note_id,))
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
@app.route("/cards/new/<int:note_id>", methods=["GET", "POST"])
def new_card(note_id):
    with get_db() as conn:
        note = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        if note is None:
            abort(404)
        if request.method == "POST":
            conn.execute(
                "INSERT INTO flashcards (note_id, subject, question, answer) VALUES (?, ?, ?, ?)",
                (note_id, note["subject"], request.form["question"], request.form["answer"]),
            )
            return redirect(url_for("cards"))
    return render_template("new_card.html", note=note)

@app.route("/cards")
def cards():
    with get_db() as conn:
        all_cards = conn.execute("SELECT * FROM flashcards ORDER BY subject, id").fetchall()
    return render_template("cards.html", cards=all_cards)

@app.route("/review")
def review():
    i = request.args.get("i", 0, type=int)
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM flashcards").fetchone()[0]
        card = conn.execute(
            "SELECT * FROM flashcards ORDER BY id LIMIT 1 OFFSET ?", (i,)
        ).fetchone()
    return render_template("review.html", card=card, i=i, total=total)
if __name__ == "__main__":
    init_db()
    app.run(debug=True)