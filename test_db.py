from app import app, db, Job, User
from datetime import datetime, timezone

with app.app_context():
    # Count all jobs
    total_jobs = Job.query.count()
    open_jobs = Job.query.filter_by(status='open').count()
    
    print(f"Total jobs in database: {total_jobs}")
    print(f"Open jobs in database: {open_jobs}")
    
    # List them
    jobs = Job.query.filter_by(status='open').all()
    for job in jobs:
        print(f"Job ID: {job.id}, Title: {job.title}, Poster: {job.poster.email}")
    
    # If no jobs, create a test job
    if open_jobs == 0:
        print("\nNo open jobs found. Creating a test job...")
        # Find first user
        user = User.query.first()
        if user:
            job = Job(
                title="Test Job Position",
                description="This is a test job description for testing purposes.",
                location="Nairobi, Kenya",
                requirements="Experience with Flask, Python, HTML/CSS",
                poster_id=user.id,
                status='open'
            )
            db.session.add(job)
            db.session.commit()
            print("Created test job!")
        else:
            print("No users found to create test job.")
