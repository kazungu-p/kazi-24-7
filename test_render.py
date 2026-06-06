from app import app
with app.app_context():
    from flask import render_template
    from app import Job
    
    jobs = Job.query.filter_by(status='open').order_by(Job.created_at.desc()).all()
    print(f"Number of jobs to render: {len(jobs)}")
    
    # Try to render the template
    try:
        result = render_template('index.html', jobs=jobs)
        # Count job-card occurrences
        count = result.count('job-card')
        print(f"Number of 'job-card' in rendered HTML: {count}")
        
        if count == 0:
            print("ERROR: No job cards found in rendered HTML!")
            # Check for empty-state
            if 'empty-state' in result:
                print("Found 'empty-state' instead")
            else:
                print("Neither job-card nor empty-state found!")
                # Show snippet
                idx = result.find('jobs-grid')
                if idx != -1:
                    print("Snippet around jobs-grid:")
                    print(result[idx:idx+500])
    except Exception as e:
        print(f"Error rendering template: {e}")
