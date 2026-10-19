import sqlite3
import random
import os
import pandas as pd
from pypdf import PdfReader
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from datetime import date, timedelta
from flask import Flask, render_template, request, redirect, url_for,abort

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB
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


@app.route("/dashboard")
def dashboard():
    conn = sqlite3.connect(DB)
    quiz = pd.read_sql_query("SELECT subject, correct FROM quiz_log", conn)
    rev = pd.read_sql_query(
        "SELECT subject, quality, datetime(reviewed_at, 'localtime') AS reviewed_at FROM review_log",
        conn,
    )
    conn.close()

    # review mein Good/Easy (quality >= 3) ko "yaad tha" maante hain
    rev["correct"] = (rev["quality"] >= 3).astype(int)

    # quiz aur review dono ko ek table mein jodo
    both = pd.concat([quiz[["subject", "correct"]], rev[["subject", "correct"]]])

    labels, values, weak = [], [], None
    if not both.empty:
        acc = (both.groupby("subject")["correct"].mean() * 100).round().sort_values()
        labels = list(acc.index)
        values = [int(v) for v in acc.values]
        weak = labels[0]  # sabse kam accuracy wala

    # pichhle 7 din mein roz kitne cards review hue
    days = [date.today() - timedelta(days=i) for i in range(6, -1, -1)]
    if not rev.empty:
        rev["day"] = pd.to_datetime(rev["reviewed_at"]).dt.date
        per_day = rev.groupby("day").size()
    else:
        per_day = pd.Series(dtype=int)
    week_counts = [int(per_day.get(d, 0)) for d in days]
    week_labels = [d.strftime("%a") for d in days]

    return render_template(
        "dashboard.html",
        labels=labels, values=values, weak=weak,
        week_labels=week_labels, week_counts=week_counts,
        total_reviews=len(rev), total_quiz=len(quiz),
    )
@app.route("/note/<int:note_id>")
def note_view(note_id):
    with get_db() as conn:
        note = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
    if note is None:
        abort(404)
    return render_template("note.html", note=note)

@app.route("/ask")
def ask():
    q = request.args.get("q", "").strip()
    results = []
    if q:
        with get_db() as conn:
            notes = conn.execute("SELECT * FROM notes").fetchall()

        # har note ko chhote units mein todo, phir 3-3 units ke tukde banao
        chunks = []
        for n in notes:
            parts = re.split(r"(?<=[.!?])\s+|\n\s*\n|•", n["content"])
            units = [" ".join(p.split()) for p in parts]
            units = [u for u in units if len(u) > 3]
            for i in range(len(units)):
                window = units[i:i + 3]
                text = "\n".join(window)
                if len(text) > 25:
                    chunks.append({
                        "text": text[:600],
                        "title": n["title"],
                        "subject": n["subject"],
                        "note_id": n["id"],
                        "start": i,
                        "end": i + len(window),
                    })

        if chunks:
            try:
                vec = TfidfVectorizer(stop_words="english")
                matrix = vec.fit_transform([c["text"] for c in chunks])
                scores = cosine_similarity(vec.transform([q]), matrix).ravel()
                for i in scores.argsort()[::-1]:
                    if scores[i] <= 0 or len(results) == 3:
                        break
                    c = chunks[i]
                    # pehle chune hue tukdon se overlap na ho
                    overlap = any(
                        r["note_id"] == c["note_id"]
                        and c["start"] < r["end"] and r["start"] < c["end"]
                        for r in results
                    )
                    if not overlap:
                        results.append(dict(c, score=round(float(scores[i]) * 100)))
            except ValueError:
                results = []
    return render_template("ask.html", q=q, results=results)

@app.route("/upload", methods=["GET", "POST"])
def upload():
    error = None
    if request.method == "POST":
        f = request.files.get("file")
        subject = request.form["subject"].strip()
        title = request.form.get("title", "").strip()
        if not f or not f.filename:
            error = "Please choose a file."
        else:
            name = f.filename
            ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
            text = None
            try:
                if ext == "txt":
                    text = f.read().decode("utf-8", errors="ignore")
                elif ext == "pdf":
                    reader = PdfReader(f.stream)
                    text = "\n".join((p.extract_text() or "") for p in reader.pages)
                    # PDF ki line-wrap wali newlines hatao, paragraph breaks rakho
                    text = re.sub(r"\n{3,}", "\n\n", text)
                else:
                    error = "Only .txt and .pdf files are supported."
            except Exception:
                error = "Could not read this file."

            if text is not None:
                text = text.strip()
                if not text:
                    error = "No text found. Scanned or handwritten files are not supported yet."
                else:
                    with get_db() as conn:
                        conn.execute(
                            "INSERT INTO notes (subject, title, content) VALUES (?, ?, ?)",
                            (subject, title or name.rsplit(".", 1)[0], text),
                        )
                    return redirect(url_for("home"))
    return render_template("upload.html", error=error)

init_db()
if __name__ == "__main__":
    app.run(debug=True)