#!/usr/bin/env python3
import re

with open('app.py', 'r') as f:
    lines = f.readlines()

output = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # Check for the problematic pattern
    if 'if request.accept_mimetypes.accept_html and not request.accept_mimetypes.accept_json:' in line and i+1 < len(lines):
        next_line = lines[i+1]
        if 'return redirect(url_for' in next_line and 'job_detail' in next_line:
            # Skip both lines (comment them out)
            output.append(f"# FIXED: {line}")
            output.append(f"# FIXED: {next_line}")
            i += 2
            continue
    
    output.append(line)
    i += 1

with open('app.py', 'w') as f:
    f.writelines(output)

print("Fixed all infinite redirect loops in app.py")
