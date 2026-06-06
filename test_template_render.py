import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, Job
from flask import render_template_string

with app.app_context():
    print("=== TESTING TEMPLATE RENDERING ===")
    
    # Get jobs as the index route does
    jobs = Job.query.filter_by(status='open').order_by(Job.created_at.desc()).limit(50).all()
    print(f"Jobs passed to template: {len(jobs)}")
    
    # Test a simple template
    test_template = """
    {% if jobs %}
      Found {{ jobs|length }} jobs
      {% for job in jobs %}
        - {{ job.title }}
      {% endfor %}
    {% else %}
      No jobs found
    {% endif %}
    """
    
    result = render_template_string(test_template, jobs=jobs)
    print("\nTemplate output:")
    print(result)
    
    # Check if there's a template caching issue
    print("\n=== CHECKING ACTUAL TEMPLATE ===")
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
    if os.path.exists(template_path):
        with open(template_path, 'r') as f:
            content = f.read()
            # Look for the jobs loop
            if '{% for job in jobs %}' in content:
                print("✓ Template has jobs loop")
            else:
                print("✗ Template missing jobs loop!")
            
            # Check for empty state
            if 'No open jobs yet' in content:
                print("✓ Template has 'No open jobs yet' text")
                
            # Count job-card occurrences
            jobcard_count = content.count('job-card')
            empty_state_count = content.count('empty-state')
            print(f"  'job-card' appears {jobcard_count} times")
            print(f"  'empty-state' appears {empty_state_count} times")
    else:
        print(f"✗ Template not found at {template_path}")
