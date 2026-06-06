import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User, Job
from werkzeug.security import generate_password_hash
from datetime import datetime, timezone

with app.app_context():
    print("=== Testing Job Posting ===")
    
    # Check current user (you're logged in as elishabwire563@gmail.com)
    user = User.query.filter_by(email="elishabwire563@gmail.com").first()
    
    if not user:
        print("❌ User not found! Creating test user...")
        user = User(
            email="test@example.com",
            username="tester",
            profile_completed=True
        )
        user.set_password("test123")
        db.session.add(user)
        db.session.commit()
        print(f"✅ Created test user ID: {user.id}")
    else:
        print(f"✅ Using existing user ID: {user.id}, Email: {user.email}")
    
    # Create a test job
    job = Job(
        title="Software Developer Job",
        description="We are looking for a skilled software developer...",
        location="Nairobi, Kenya",
        requirements="Python, Flask, SQL, 3+ years experience",
        poster_id=user.id,
        status="open"
    )
    
    db.session.add(job)
    db.session.commit()
    
    print(f"\n✅ Successfully posted job!")
    print(f"   Job ID: {job.id}")
    print(f"   Title: '{job.title}'")
    print(f"   Description: '{job.description[:50]}...'")
    print(f"   Status: {job.status}")
    
    # Verify job appears in database
    all_jobs = Job.query.all()
    print(f"\n📊 Total jobs in database: {len(all_jobs)}")
    for j in all_jobs:
        print(f"   - Job {j.id}: '{j.title}' by User {j.poster_id}")
    
    # Check user's jobs specifically
    user_jobs = Job.query.filter_by(poster_id=user.id).all()
    print(f"\n📊 User {user.id} has {len(user_jobs)} jobs posted:")
    for j in user_jobs:
        print(f"   - Job {j.id}: '{j.title}'")
    
    print("\n🎉 Test complete! Now check http://127.0.0.1:5000/profile in your browser")
