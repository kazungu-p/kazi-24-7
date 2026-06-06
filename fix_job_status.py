import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, Job

with app.app_context():
    print("=== CHECKING JOB STATUS ===")
    
    # Get all jobs
    jobs = Job.query.all()
    
    for job in jobs:
        print(f"Job {job.id}: '{job.title}' - Status: '{job.status}'")
        
        # Fix if status is not 'open'
        if job.status != 'open':
            print(f"  ⚠️  Changing status from '{job.status}' to 'open'")
            job.status = 'open'
    
    db.session.commit()
    print("\n✅ Updated all jobs to 'open' status")
    
    # Verify
    open_jobs = Job.query.filter_by(status='open').all()
    print(f"\nOpen jobs after fix: {len(open_jobs)}")
