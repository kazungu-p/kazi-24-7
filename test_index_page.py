import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, Job

with app.app_context():
    print("=== INDEX PAGE DATA ===")
    
    # This is what the index() route does
    jobs = Job.query.filter_by(status='open').order_by(Job.created_at.desc()).limit(50).all()
    
    print(f"Number of open jobs: {len(jobs)}")
    
    if jobs:
        print("\nOpen jobs that SHOULD appear on homepage:")
        for job in jobs:
            print(f"  - {job.title} (ID: {job.id})")
    else:
        print("⚠️  No open jobs found! This is why homepage shows 'No open jobs yet'")
        
        # Check if job exists but with wrong status
        all_jobs = Job.query.all()
        print(f"\nAll jobs in database (any status): {len(all_jobs)}")
        for job in all_jobs:
            print(f"  - {job.title} (ID: {job.id}, Status: '{job.status}')")
