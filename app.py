import sqlite3
import random
import os
from datetime import date, timedelta
from flask import Flask, render_template, request, redirect, url_for,abort

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "studyforge.db")

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def sm2(ease, interval, reps, quality):
    if quality < 3:
        reps = 0
        interval = 1
    else:
        if reps == 0:
            interval = 1
        elif reps == 1:
            interval = 6
        else:
            interval = round(interval * ease)
        reps += 1
    ease = ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    ease = max(1.3, ease)
    return ease, interval, reps

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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS review_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                quality INTEGER NOT NULL,
                reviewed_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS quiz_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                correct INTEGER NOT NULL,
                taken_at TEXT DEFAULT CURRENT_TIMESTAMP
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
    today = date.today().isoformat()
    with get_db() as conn:
        due = conn.execute(
            "SELECT COUNT(*) FROM flashcards WHERE next_review <= ?", (today,)
        ).fetchone()[0]
        card = conn.execute(
            "SELECT * FROM flashcards WHERE next_review <= ? ORDER BY next_review, id LIMIT 1",
            (today,),
        ).fetchone()
    return render_template("review.html", card=card, due=due)

@app.route("/review/<int:card_id>", methods=["POST"])
def rate(card_id):
    quality = {"again": 1, "good": 4, "easy": 5}.get(request.form.get("rating"))
    if quality is None:
        abort(400)
    with get_db() as conn:
        card = conn.execute("SELECT * FROM flashcards WHERE id = ?", (card_id,)).fetchone()
        if card is None:
            abort(404)
        ease, interval, reps = sm2(
            card["ease"], card["interval_days"], card["repetitions"], quality
        )
        next_review = (date.today() + timedelta(days=interval)).isoformat()
        conn.execute(
            "UPDATE flashcards SET ease = ?, interval_days = ?, repetitions = ?, next_review = ? WHERE id = ?",
            (ease, interval, reps, next_review, card_id),
        )
        conn.execute(
            "INSERT INTO review_log (card_id, subject, quality) VALUES (?, ?, ?)",
            (card_id, card["subject"], quality),
        )
    return redirect(url_for("review"))

@app.route("/quiz")
@app.route("/quiz")
def quiz():
    with get_db() as conn:
        subjects = conn.execute("""
            SELECT f.subject AS subject,
                   COUNT(*) AS cards,
                   (SELECT COUNT(*) FROM quiz_log q WHERE q.subject = f.subject) AS attempts,
                   (SELECT COALESCE(SUM(correct), 0) FROM quiz_log q WHERE q.subject = f.subject) AS num_correct
            FROM flashcards f
            GROUP BY f.subject
            ORDER BY f.subject
        """).fetchall()
    return render_template("quiz_select.html", subjects=subjects)

@app.route("/quiz/<subject>")
def quiz_subject(subject):
    with get_db() as conn:
        all_cards = conn.execute("SELECT * FROM flashcards").fetchall()
    subject_cards = [c for c in all_cards if c["subject"] == subject]
    if not subject_cards or len(all_cards) < 2:
        return render_template("quiz.html", questions=[], subject=subject)
    picked = random.sample(subject_cards, min(5, len(subject_cards)))
    questions = []
    for c in picked:
        same = [x["answer"] for x in subject_cards
                if x["id"] != c["id"] and x["answer"] != c["answer"]]
        other = [x["answer"] for x in all_cards
                 if x["subject"] != subject and x["answer"] != c["answer"]]
        random.shuffle(same)
        random.shuffle(other)
        distractors = list(dict.fromkeys(same + other))[:3]
        options = distractors + [c["answer"]]
        random.shuffle(options)
        questions.append({"card": c, "options": options})
    return render_template("quiz.html", questions=questions, subject=subject)

@app.route("/quiz/submit", methods=["POST"])
def quiz_submit():
    ids = request.form.getlist("card_id", type=int)
    results = []
    with get_db() as conn:
        for cid in ids:
            card = conn.execute("SELECT * FROM flashcards WHERE id = ?", (cid,)).fetchone()
            if card is None:
                continue
            chosen = request.form.get(f"answer_{cid}", "")
            correct = chosen == card["answer"]
            conn.execute(
                "INSERT INTO quiz_log (card_id, subject, correct) VALUES (?, ?, ?)",
                (cid, card["subject"], int(correct)),
            )
            results.append({"card": card, "chosen": chosen, "correct": correct})
    score = sum(r["correct"] for r in results)
    subject = results[0]["card"]["subject"] if results else ""
    return render_template("quiz_result.html", results=results, score=score,
    total=len(results), subject=subject)

init_db()
if __name__ == "__main__":
    app.run(debug=True)