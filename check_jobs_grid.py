import re

with open('templates/index.html', 'r') as f:
    content = f.read()

# Find the jobs-grid section
# First, let's find the div with class "jobs-grid"
pattern = r'(<div[^>]*class=["\'][^"\']*jobs-grid[^"\']*["\'][^>]*>.*?</div>\s*</div>)'
match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)

if match:
    jobs_grid = match.group(1)
    print("Found jobs-grid section:")
    print("=" * 80)
    
    # Simplify for readability
    simplified = re.sub(r'\s+', ' ', jobs_grid)
    print(simplified[:500] + "..." if len(simplified) > 500 else simplified)
    print("=" * 80)
    
    # Check what's inside
    if '{% if jobs %}' in jobs_grid:
        print("\n✓ Contains '{% if jobs %}'")
        
        # Extract the template logic
        logic_start = jobs_grid.find('{%')
        logic_end = jobs_grid.rfind('%}') + 2
        template_logic = jobs_grid[logic_start:logic_end]
        
        print("\nTemplate logic found:")
        print(template_logic)
        
        # Count job cards
        job_card_count = jobs_grid.count('job-card')
        print(f"\nNumber of 'job-card' strings: {job_card_count}")
        
        # Count empty-state
        empty_state_count = jobs_grid.count('empty-state')
        print(f"Number of 'empty-state' strings: {empty_state_count}")
        
        if job_card_count > 0 and empty_state_count > 0:
            print("\n⚠️  WARNING: Both job-card AND empty-state are present!")
            print("   This likely means the template shows BOTH when jobs exist.")
            print("   The empty-state might be covering/hiding the job cards.")
    else:
        print("\n✗ Does NOT contain '{% if jobs %}'")
        print("   The template might have wrong variable name or no conditional.")
else:
    print("Could not find jobs-grid section")
