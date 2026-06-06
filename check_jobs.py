import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'job_platform.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tables in database:", tables)

# Check jobs
cursor.execute("SELECT COUNT(*) FROM job WHERE status='open';")
open_jobs = cursor.fetchone()[0]
print(f"Open jobs: {open_jobs}")

if open_jobs > 0:
    cursor.execute("SELECT id, title, status, poster_id FROM job WHERE status='open' LIMIT 5;")
    jobs = cursor.fetchall()
    print("\nSample open jobs:")
    for job in jobs:
        print(f"  ID: {job[0]}, Title: {job[1]}, Status: {job[2]}, Poster ID: {job[3]}")

# Check users
cursor.execute("SELECT COUNT(*) FROM user;")
user_count = cursor.fetchone()[0]
print(f"\nTotal users: {user_count}")

cursor.execute("SELECT id, email, username FROM user LIMIT 5;")
users = cursor.fetchall()
print("Sample users:")
for user in users:
    print(f"  ID: {user[0]}, Email: {user[1]}, Username: {user[2]}")

conn.close()
