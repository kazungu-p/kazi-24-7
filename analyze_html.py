import sys
import os
import re

# Read the saved homepage
with open('homepage.html', 'r') as f:
    html = f.read()

print("=== ANALYZING HOMEPAGE HTML ===")

# Find the jobs-grid section
jobs_grid_start = html.find('<div class="jobs-grid">')
if jobs_grid_start == -1:
    print("❌ No jobs-grid found!")
    sys.exit(1)

jobs_grid_end = html.find('</div>', jobs_grid_start) + 6
jobs_grid_html = html[jobs_grid_start:jobs_grid_end]

print(f"\nJobs grid HTML ({len(jobs_grid_html)} chars):")
print("=" * 50)
print(jobs_grid_html[:500] + "..." if len(jobs_grid_html) > 500 else jobs_grid_html)
print("=" * 50)

# Count job cards
job_cards = re.findall(r'<div class="job-card"', jobs_grid_html)
print(f"\n✅ Found {len(job_cards)} job-card divs in jobs-grid")

# Check if empty-state is also present
if 'empty-state' in jobs_grid_html:
    print("⚠️  WARNING: empty-state div is ALSO present in jobs-grid!")
    print("   This means BOTH job cards AND empty state are showing")
    print("   The empty state might be covering/hiding the job cards")
    
    # Extract empty state HTML
    empty_start = jobs_grid_html.find('<div class="empty-state">')
    empty_end = jobs_grid_html.find('</div>', empty_start) + 6
    empty_html = jobs_grid_html[empty_start:empty_end]
    print(f"\nEmpty state HTML ({len(empty_html)} chars):")
    print(empty_html[:200] + "..." if len(empty_html) > 200 else empty_html)

# Check CSS that might hide job cards
print("\n=== CHECKING FOR HIDING CSS ===")
css_hiding_patterns = [
    (r'\.job-card\s*{[^}]*display:\s*none', 'display: none on job-card'),
    (r'\.job-card\s*{[^}]*visibility:\s*hidden', 'visibility: hidden on job-card'),
    (r'\.job-card\s*{[^}]*opacity:\s*0', 'opacity: 0 on job-card'),
    (r'\.job-card\s*{[^}]*height:\s*0', 'height: 0 on job-card'),
]

for pattern, description in css_hiding_patterns:
    if re.search(pattern, html, re.IGNORECASE | re.DOTALL):
        print(f"❌ Found: {description}")
    else:
        print(f"✓ Not found: {description}")

print("\n=== RECOMMENDATION ===")
if len(job_cards) > 0:
    print("1. Jobs ARE in HTML but might be hidden by CSS or overlapped by empty-state")
    print("2. Try adding this CSS to force show job cards:")
    print("""
    <style>
    .job-card {
        display: block !important;
        position: relative !important;
        z-index: 100 !important;
    }
    .empty-state {
        display: none !important;
    }
    </style>
    """)
