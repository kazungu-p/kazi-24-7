import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User, Job

with app.app_context():
    # Create test user
    user = User.query.filter_by(email="browser@test.com").first()
    if not user:
        user = User(
            email="browser@test.com",
            username="browsertester",
            profile_completed=True
        )
        user.set_password("test123")
        db.session.add(user)
        db.session.commit()
        print(f"Created user: browser@test.com / test123")
    
    # Create test job
    job = Job(
        title="Web Developer Needed",
        description="Join our team as a web developer...",
        location="Remote",
        requirements="HTML, CSS, JavaScript",
        poster_id=user.id
    )
    db.session.add(job)
    db.session.commit()
    
    print(f"Created job: '{job.title}'")
    print("\nNow login in browser with:")
    print("  Email: browser@test.com")
    print("  Password: test123")
