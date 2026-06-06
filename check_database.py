import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User, Job

with app.app_context():
    print("=== DATABASE CHECK ===")
    
    # Count all jobs
    job_count = Job.query.count()
    print(f"Total jobs in database: {job_count}")
    
    # List all jobs
    all_jobs = Job.query.all()
    for job in all_jobs:
        print(f"\nJob ID: {job.id}")
        print(f"  Title: '{job.title}'")
        print(f"  Status: {job.status}")
        print(f"  Poster ID: {job.poster_id}")
        
        # Get poster info
        poster = User.query.get(job.poster_id)
        if poster:
            print(f"  Poster Email: {poster.email}")
            print(f"  Poster Username: {poster.username}")
    
    # Check users
    print(f"\n=== USERS ===")
    users = User.query.all()
    for user in users:
        user_jobs = Job.query.filter_by(poster_id=user.id).all()
        print(f"User {user.id}: {user.email} - {len(user_jobs)} jobs")
