import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from flask import render_template_string

with app.test_client() as client:
    # Test 1: Get raw response
    print("=== TEST 1: Raw HTTP Response ===")
    response = client.get('/')
    print(f"Status: {response.status_code}")
    
    # Test 2: Check if jobs are in HTML
    html = response.get_data(as_text=True)
    
    # Look for job titles in HTML
    job_titles = ['Software Developer Job', 'Web Developer Needed']
    found_jobs = []
    for title in job_titles:
        if title in html:
            found_jobs.append(title)
    
    if found_jobs:
        print(f"\n✅ Found {len(found_jobs)} job titles in HTML:")
        for title in found_jobs:
            print(f"  - {title}")
    else:
        print("\n❌ No job titles found in HTML!")
        print("   This means template isn't rendering jobs")
        
    # Test 3: Check template variables
    print("\n=== TEST 3: Direct Template Test ===")
    with app.app_context():
        from app import Job
        jobs = Job.query.filter_by(status='open').all()
        
        simple_template = """
        <div class="test-jobs">
        {% if jobs %}
          JOBS FOUND: {{ jobs|length }}
          {% for job in jobs %}
          <div class="test-job">{{ job.title }}</div>
          {% endfor %}
        {% else %}
          NO JOBS IN TEMPLATE
        {% endif %}
        </div>
        """
        
        result = render_template_string(simple_template, jobs=jobs)
        print("Template output preview:")
        print(result[:500])
