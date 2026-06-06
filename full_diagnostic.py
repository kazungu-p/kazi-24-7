import sys
import os
import subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, Job, User

print("=" * 60)
print("FULL DIAGNOSTIC FOR JOB VISIBILITY")
print("=" * 60)

with app.app_context():
    # 1. Database check
    print("\n1. DATABASE STATUS:")
    total_jobs = Job.query.count()
    open_jobs = Job.query.filter_by(status='open').count()
    print(f"   Total jobs: {total_jobs}")
    print(f"   Open jobs: {open_jobs}")
    
    # 2. List all jobs
    print("\n2. ALL JOBS IN DATABASE:")
    jobs = Job.query.all()
    for job in jobs:
        poster = User.query.get(job.poster_id)
        poster_email = poster.email if poster else f"User {job.poster_id} (deleted?)"
        print(f"   - ID {job.id}: '{job.title}'")
        print(f"     Status: '{job.status}' | Poster: {poster_email}")
    
    # 3. What index() route would show
    print("\n3. WHAT HOMEPAGE SHOULD SHOW:")
    homepage_jobs = Job.query.filter_by(status='open').order_by(Job.created_at.desc()).limit(50).all()
    if homepage_jobs:
        print(f"   ✓ {len(homepage_jobs)} open jobs should appear on homepage")
        for job in homepage_jobs:
            print(f"     • {job.title}")
    else:
        print("   ✗ No open jobs - homepage will show 'No open jobs yet'")
    
    # 4. Check specific job
    print("\n4. CHECKING JOB ID 1:")
    job1 = Job.query.get(1)
    if job1:
        print(f"   ✓ Job exists: '{job1.title}'")
        print(f"     Status: '{job1.status}'")
        print(f"     Created: {job1.created_at}")
        
        if job1.status != 'open':
            print(f"   ⚠️  PROBLEM: Job status is '{job1.status}', not 'open'!")
            print(f"     Fix: UPDATE job SET status='open' WHERE id=1;")
        else:
            print(f"   ✓ Job status is 'open' - should appear on homepage")
    else:
        print("   ✗ Job ID 1 not found!")

print("\n" + "=" * 60)
print("RECOMMENDED FIXES:")
print("1. If job status is not 'open': Run fix_job_status.py")
print("2. Restart Flask server: pkill -f 'flask run'; flask run")
print("3. Clear browser cache or try incognito window")
print("4. Check browser console for errors (F12 → Console)")
print("=" * 60)
