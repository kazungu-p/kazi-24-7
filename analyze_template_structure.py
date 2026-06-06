import re
import os

template_path = 'templates/index.html'
if not os.path.exists(template_path):
    print(f"Template not found: {template_path}")
    exit(1)

with open(template_path, 'r') as f:
    content = f.read()

print("=== ANALYZING TEMPLATE STRUCTURE ===")

# Find jobs-grid div
pattern = r'<div[^>]*class="jobs-grid"[^>]*>(.*?)</div>\s*</div>'
match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)

if not match:
    print("❌ Could not find jobs-grid div")
    # Try simpler pattern
    pattern = r'<div[^>]*class=["\']jobs-grid["\'][^>]*>(.*?)</div>'
    match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)

if match:
    grid_content = match.group(0)
    print(f"\nFound jobs-grid div ({len(grid_content)} chars)")
    print("=" * 80)
    
    # Extract just the template logic part
    logic_start = grid_content.find('{%')
    if logic_start != -1:
        logic_end = grid_content.rfind('%}') + 2
        template_logic = grid_content[logic_start:logic_end]
        print("Template logic inside jobs-grid:")
        print(template_logic)
        
        # Check structure
        if '{% if jobs %}' in template_logic or '{% if jobs|length %}' in template_logic:
            print("\n✓ Template checks 'jobs' variable")
            
            # Count occurrences
            if_count = template_logic.count('{% if')
            else_count = template_logic.count('{% else')
            endif_count = template_logic.count('{% endif')
            
            print(f"\nTemplate block counts:")
            print(f"  {% if ... %} : {if_count}")
            print(f"  {% else %}   : {else_count}")
            print(f"  {% endif %}  : {endif_count}")
            
            if if_count == 1 and else_count == 1 and endif_count == 1:
                print("✓ Balanced if/else/endif structure")
            else:
                print("⚠️  Unbalanced if/else structure!")
                
                # Show the actual structure
                lines = template_logic.split('\n')
                print("\nActual template lines:")
                for i, line in enumerate(lines):
                    if '{%' in line or '%}' in line:
                        print(f"  Line: {line.strip()}")
        else:
            print("\n❌ Template does NOT check 'jobs' variable!")
    else:
        print("\n❌ No template logic found inside jobs-grid!")
        
    print("\n" + "=" * 80)
    
    # Check if BOTH job cards and empty state exist
    has_job_card = 'job-card' in grid_content
    has_empty_state = 'empty-state' in grid_content
    
    print(f"\nContains 'job-card': {has_job_card}")
    print(f"Contains 'empty-state': {has_empty_state}")
    
    if has_job_card and has_empty_state:
        print("⚠️  WARNING: BOTH job-card AND empty-state are in the template!")
        print("   This means jobs are rendered but might be hidden by empty-state")
        
        # Check order
        job_card_pos = grid_content.find('job-card')
        empty_state_pos = grid_content.find('empty-state')
        
        if job_card_pos < empty_state_pos:
            print("   ✓ job-card appears BEFORE empty-state")
        else:
            print("   ⚠️  empty-state appears BEFORE job-card (might cover it)")
    elif has_job_card and not has_empty_state:
        print("✓ Only job-card is present (good when jobs exist)")
    elif not has_job_card and has_empty_state:
        print("✓ Only empty-state is present (when no jobs)")
else:
    print("❌ No jobs-grid found in template")
