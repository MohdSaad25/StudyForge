"""Fill StudyForge with demo data: notes, flashcards, review and quiz history.

Run from the studyforge folder with the venv active:
    python seed.py            # only runs if there are no notes yet
    python seed.py --force    # deletes ALL existing data first, then seeds
"""
import random
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone

import app  # reuses DB path and init_db() from app.py

random.seed(7)

# subject -> list of (note title, note content, [(question, answer), ...])
DEMO = {
    "Java": [
        (
            "Constructors",
            "A constructor is a special method whose name is the same as the class name. "
            "It is called automatically when an object is created. "
            "A constructor has no explicit return type. "
            "A copy constructor creates a new object by copying the values of an existing object.",
            [
                ("What is a constructor?", "A special method with the same name as the class, called when an object is created."),
                ("Does a constructor have a return type?", "No, a constructor has no explicit return type."),
                ("What is a copy constructor?", "A constructor that creates a new object by copying the values of an existing object."),
            ],
        ),
        (
            "Inheritance",
            "Inheritance lets a class acquire the properties and methods of another class. "
            "The class that inherits is called the subclass or child class. "
            "The class being inherited from is called the superclass or parent class. "
            "Java uses the extends keyword for inheritance. "
            "Java does not support multiple inheritance of classes.",
            [
                ("What is inheritance?", "A class acquires the properties and methods of another class."),
                ("Which keyword is used for inheritance in Java?", "The extends keyword."),
                ("Does Java support multiple inheritance of classes?", "No. Interfaces can be used instead."),
            ],
        ),
    ],
    "DBMS": [
        (
            "Normalization",
            "Normalization is the process of organizing data to reduce redundancy. "
            "1NF requires atomic values and no repeating groups. "
            "2NF removes partial dependency on a composite key. "
            "3NF removes transitive dependency. "
            "BCNF is a stricter version of 3NF.",
            [
                ("Why do we normalize a database?", "To reduce redundancy and improve data integrity."),
                ("What does 2NF remove?", "Partial dependency on a composite key."),
                ("What does 3NF remove?", "Transitive dependency."),
            ],
        ),
        (
            "Transactions and ACID",
            "A transaction is a group of operations treated as a single unit. "
            "ACID stands for Atomicity, Consistency, Isolation and Durability. "
            "Atomicity means all operations succeed or none do. "
            "Durability means committed changes survive a crash.",
            [
                ("What does ACID stand for?", "Atomicity, Consistency, Isolation and Durability."),
                ("What is atomicity?", "All operations of a transaction succeed, or none of them do."),
                ("What is durability?", "Committed changes survive a crash."),
            ],
        ),
    ],
    "OS": [
        (
            "Deadlock",
            "Deadlock happens when processes wait for each other forever. "
            "It needs four conditions: mutual exclusion, hold and wait, no preemption and circular wait. "
            "Breaking any one of these conditions prevents deadlock.",
            [
                ("What is deadlock?", "A situation where processes wait for each other forever."),
                ("Name the four conditions for deadlock.", "Mutual exclusion, hold and wait, no preemption and circular wait."),
                ("How can deadlock be prevented?", "By breaking at least one of the four conditions."),
            ],
        ),
        (
            "CPU Scheduling",
            "CPU scheduling decides which process runs next. "
            "First Come First Served runs processes in arrival order. "
            "Shortest Job First picks the process with the smallest burst time. "
            "Round Robin gives each process a fixed time slice called a quantum.",
            [
                ("What does FCFS do?", "Runs processes in the order they arrive."),
                ("What does Shortest Job First pick?", "The process with the smallest burst time."),
                ("What is a time quantum in Round Robin?", "A fixed time slice given to each process."),
            ],
        ),
    ],
}

# chance of a correct answer per subject, so the dashboard has a clear weak subject
ACCURACY = {"Java": 0.85, "DBMS": 0.70, "OS": 0.45}


def stamp(days_ago):
    t = datetime.now(timezone.utc) - timedelta(days=days_ago, minutes=random.randint(0, 300))
    return t.strftime("%Y-%m-%d %H:%M:%S")


def main():
    force = "--force" in sys.argv
    app.init_db()
    conn = sqlite3.connect(app.DB)

    existing = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
    if existing and not force:
        print(f"{existing} notes already exist, nothing changed. Use --force to wipe and reseed.")
        conn.close()
        return
    if force:
        for table in ("quiz_log", "review_log", "flashcards", "notes"):
            conn.execute(f"DELETE FROM {table}")

    cards = []  # (card_id, subject)
    for subject, notes in DEMO.items():
        for title, content, qa in notes:
            cur = conn.execute(
                "INSERT INTO notes (subject, title, content) VALUES (?, ?, ?)",
                (subject, title, content),
            )
            note_id = cur.lastrowid
            for q, a in qa:
                due_in = random.choice([0, 0, 1, 2, 4])
                cur = conn.execute(
                    "INSERT INTO flashcards (note_id, subject, question, answer, ease, "
                    "interval_days, repetitions, next_review) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        note_id, subject, q, a,
                        round(random.uniform(2.1, 2.7), 2),
                        max(1, due_in), random.randint(1, 3),
                        (date.today() + timedelta(days=due_in)).isoformat(),
                    ),
                )
                cards.append((cur.lastrowid, subject))

    # review history over the last 7 days (quality 1 = Again, 4 = Good, 5 = Easy)
    for days_ago in range(6, -1, -1):
        for _ in range(random.randint(1, 5)):
            card_id, subject = random.choice(cards)
            quality = random.choice([4, 5]) if random.random() < ACCURACY[subject] else 1
            conn.execute(
                "INSERT INTO review_log (card_id, subject, quality, reviewed_at) VALUES (?, ?, ?, ?)",
                (card_id, subject, quality, stamp(days_ago)),
            )

    # quiz history
    for _ in range(45):
        card_id, subject = random.choice(cards)
        correct = 1 if random.random() < ACCURACY[subject] else 0
        conn.execute(
            "INSERT INTO quiz_log (card_id, subject, correct, taken_at) VALUES (?, ?, ?, ?)",
            (card_id, subject, correct, stamp(random.randint(0, 6))),
        )

    conn.commit()
    conn.close()
    print(f"Seeded {sum(len(n) for n in DEMO.values())} notes and {len(cards)} flashcards with demo history.")


if __name__ == "__main__":
    main()
