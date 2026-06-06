import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User, Job
from werkzeug.security import generate_password_hash

with app.app_context():
    # Check all jobs in database
    all_jobs = Job.query.all()
    print(f"\n=== ALL JOBS IN DATABASE ({len(all_jobs)}) ===")
    for job in all_jobs:
        print(f"ID: {job.id}, Title: '{job.title}', Poster: {job.poster_id}, Status: {job.status}")
    
    # Check users
    users = User.query.all()
    print(f"\n=== ALL USERS ({len(users)}) ===")
    for user in users:
        user_jobs = Job.query.filter_by(poster_id=user.id).all()
        print(f"User ID: {user.id}, Email: {user.email}, Jobs: {len(user_jobs)}")
