with open('app.py', 'r') as f:
    content = f.read()

# Find the debug-check endpoint and fix its indentation
import re

# Find the pattern and fix indentation
pattern = r'(@app\.route\(\'/debug-check\'\).*?\n)(def debug_check\(\):.*?\n)(\s+""".*?"""\s*\n)(\s+jobs =.*?\n)(\s+return jsonify\(\{.*?\n)(\s+\'total_jobs\': len\(jobs\),.*?\n)(\s+\'jobs_exist\':.*?\n)(\s+\'sample_jobs\':.*?\n)(\s+\}\)\n)(\s+\))'

# Simple fix: just ensure proper indentation
# Let's find the function and rewrite it
lines = content.split('\n')
new_lines = []
i = 0
while i < len(lines):
    if lines[i].strip() == '@app.route(\'/debug-check\')':
        # Found it, replace with properly indented version
        new_lines.append(lines[i])  # Keep route decorator
        i += 1
        # Add the function with proper indentation
        new_lines.append('def debug_check():')
        new_lines.append('    """Debug endpoint to check jobs data"""')
        new_lines.append('    jobs = Job.query.filter_by(status=\'open\').order_by(Job.created_at.desc()).all()')
        new_lines.append('    return jsonify({')
        new_lines.append('        \'total_jobs\': len(jobs),')
        new_lines.append('        \'jobs_exist\': len(jobs) > 0,')
        new_lines.append('        \'sample_jobs\': [{')
        new_lines.append('            \'id\': j.id,')
        new_lines.append('            \'title\': j.title,')
        new_lines.append('            \'status\': j.status,')
        new_lines.append('            \'poster_id\': j.poster_id')
        new_lines.append('        } for j in jobs[:3]]')
        new_lines.append('    })')
        # Skip the old function lines
        while i < len(lines) and (lines[i].strip() == '' or lines[i].startswith(' ') or lines[i].startswith('def ') or lines[i].startswith('    ')):
            i += 1
    else:
        new_lines.append(lines[i])
        i += 1

# Write back
with open('app.py', 'w') as f:
    f.write('\n'.join(new_lines))

print("Fixed debug-check endpoint indentation!")
