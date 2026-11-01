# StudyForge

A study assistant web app: keep subject-wise notes, turn them into flashcards, revise with spaced repetition, take quizzes, search your notes, and track progress on a dashboard.

Built with Flask, SQLite, Pandas and scikit-learn.

<!-- Add screenshots here: home, review, quiz, dashboard, ask -->
<!-- ![Home](screenshots/home.png) -->

**Live demo:** _add link after deploying_

## Features

- **Notes**: add, edit, delete, and filter by subject. Upload typed `.txt` or text-based `.pdf` files and the text becomes a note.
- **Flashcards**: create question/answer cards from any note.
- **Spaced repetition**: a simplified SM-2 algorithm. After each review you rate the card Again / Good / Easy, and the app schedules its next review date based on how well you remember it.
- **Quizzes**: subject-wise multiple-choice quizzes generated from your flashcards, with a score and per-subject accuracy.
- **Progress dashboard**: Pandas analysis of review and quiz history. Shows accuracy by subject, flags the weakest subject, and charts cards reviewed over the last 7 days.
- **Ask your notes**: type a question and get the most relevant passages from your notes, ranked with TF-IDF and cosine similarity.

## How it works

| Part | Approach |
|---|---|
| Spaced repetition | SM-2: each card has an ease factor, interval and repetition count. Again/Good/Easy map to quality 1/4/5. |
| Dashboard | `review_log` and `quiz_log` are read into DataFrames, combined, and grouped by subject (`groupby` + `mean`). |
| Ask your notes | Notes are split into sentences, grouped into 3-sentence windows, vectorised with TF-IDF, and ranked by cosine similarity to the question. |
| PDF import | Text is extracted with `pypdf`. Scanned or handwritten PDFs are not supported. |

## Tech stack

Flask, Jinja2, SQLite, Pandas, scikit-learn, pypdf, Chart.js, HTML/CSS/JS.

## Run locally

```bash
git clone <your-repo-url>
cd studyforge
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

### Demo data

To fill the app with sample notes, flashcards and review history (useful for screenshots and the dashboard):

```bash
python seed.py            # only runs on an empty database
python seed.py --force    # wipes existing data first
```

## Project structure

```
studyforge/
├── app.py            # routes, database, SM-2, dashboard, search
├── seed.py           # demo data
├── requirements.txt
├── static/style.css
└── templates/        # base.html and one template per page
```

## Limitations

- Search matches words, not meaning. "stuck processes" will not find a note that says "deadlock".
- Only typed text is imported. Handwritten notes need OCR, which is not built yet.
- Single-user, no login. The SQLite database is local to wherever the app runs.

## Future scope

- Upload handwritten notes (OCR with a vision model, with a review-and-edit step)
- Login and sharing notes between students
- An LLM-powered "ask" mode that answers in sentences using only the retrieved notes (RAG)
- Study streaks and a "due today" summary on the home page

## Author

Your Name, Data Science student
