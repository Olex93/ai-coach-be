import sqlite3
from config import settings
from datetime import datetime, timedelta


def get_database_connection():
    connection = sqlite3.connect(settings.DATABASE_PATH)
    return connection


def create_database_and_tables():
    connection = get_database_connection()
    cursor = connection.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        email VARCHAR(255) NOT NULL UNIQUE,
        hashed_password VARCHAR(255) NOT NULL,
        height INTEGER,
        weight INTEGER,
        age INTEGER,
        gender VARCHAR(100),
        goals TEXT,
        verified BOOLEAN NOT NULL DEFAULT 0
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS workouts (
        workout_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date DATE NOT NULL,
        exercise VARCHAR(100) NOT NULL,
        reps INTEGER,
        duration INTEGER,
        additional_details TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS verification_codes (
        email VARCHAR(255) NOT NULL,
        code VARCHAR(6) NOT NULL,
        expiration TIMESTAMP NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    connection.commit()
    connection.close()


def get_user_from_database(email: str):
    connection = get_database_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    connection.close()
    if user:
        return {
            "user_id": user[0],
            "email": user[1],
            "hashed_password": user[2],
            "height": user[3],
            "weight": user[4],
            "age": user[5],
            "gender": user[6],
            "goals": user[7],
            "verified": user[8],
        }
    return None


def create_user_in_database(email: str, hashed_password: str):
    connection = get_database_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("""
        INSERT INTO users (email, hashed_password, verified)
        VALUES (?, ?, 0)
        """, (email, hashed_password))
        connection.commit()
    finally:
        connection.close()


def update_user_details(email: str, height: int, weight: int, age: int, gender: str, goals: str):
    connection = get_database_connection()
    cursor = connection.cursor()
    cursor.execute("""
    UPDATE users
    SET height = ?, weight = ?, age = ?, gender = ?, goals = ?
    WHERE email = ?
    """, (height, weight, age, gender, goals, email))
    connection.commit()
    connection.close()


def save_verification_code(email, code):
    connection = get_database_connection()
    cursor = connection.cursor()
    expiration = datetime.now() + timedelta(minutes=30)  # Set expiration time
    cursor.execute("""
    INSERT INTO verification_codes (email, code, created_at, expiration)
    VALUES (?, ?, CURRENT_TIMESTAMP, ?)
    """, (email, code, expiration.strftime("%Y-%m-%d %H:%M:%S")))
    connection.commit()
    connection.close()


def get_verification_code(email: str):
    connection = get_database_connection()
    cursor = connection.cursor()
    cursor.execute("""
        SELECT code, created_at, expiration FROM verification_codes WHERE email = ? ORDER BY created_at DESC LIMIT 1
    """, (email,))
    result = cursor.fetchone()
    connection.close()
    if result:
        code, created_at, expiration_str = result
        expiration = datetime.strptime(expiration_str, "%Y-%m-%d %H:%M:%S")
        if datetime.now() > expiration:
            return None
        return code, expiration
    return None


def verify_user_in_database(email: str):
    connection = get_database_connection()
    cursor = connection.cursor()
    cursor.execute("""
    UPDATE users
    SET verified = 1
    WHERE email = ?
    """, (email,))
    connection.commit()
    connection.close()


def save_workout_log(user_id: int, workout_data: dict):
    connection = get_database_connection()
    cursor = connection.cursor()
    for workout in workout_data:
        cursor.execute("""
        INSERT INTO workouts (user_id, date, exercise, reps, duration, additional_details)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            workout.get("date"),
            workout.get("exercise"),
            workout.get("reps"),
            workout.get("duration"),
            workout.get("additional_details"),
        ))
    connection.commit()
    connection.close()


def get_workouts_from_database(user_id: int):
    connection = get_database_connection()
    cursor = connection.cursor()
    cursor.execute("""
    SELECT date, exercise, reps, duration, additional_details
    FROM workouts
    WHERE user_id = ?
    """, (user_id,))
    workouts = cursor.fetchall()
    connection.close()
    return [
        {
            "date": workout[0],
            "exercise": workout[2],
            "reps": workout[3],
            "duration": workout[4],
            "additional_details": workout[5],
        }
        for workout in workouts
    ]


def get_formatted_workout_data(user_id: int) -> str:
    workouts = get_workouts_from_database(user_id)
    workout_summary = "Here is the user's workout data: \n" + "\n".join(
        [
            f"{workout['date']} - {workout['exercise']} for {workout['reps']} reps, "
            f"duration: {workout['duration']} mins. "
            f"Notes: {workout['additional_details']}"
            for workout in workouts
        ]
    )
    return workout_summary
