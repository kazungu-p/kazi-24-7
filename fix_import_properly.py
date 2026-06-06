with open('app.py', 'r') as f:
    lines = f.readlines()

# Find the flask import line
for i, line in enumerate(lines):
    if line.strip().startswith('from flask import'):
        print(f"Found import at line {i+1}: {line.strip()}")
        
        # Check if it's multi-line or single-line
        if '(' in line:
            # Multi-line import - add render_template_string to first line
            lines[i] = 'from flask import (render_template_string,\n'
        else:
            # Single-line import - add to existing
            parts = line.strip().split('import ')
            if len(parts) == 2:
                current_imports = parts[1]
                lines[i] = f'from flask import render_template_string, {current_imports}\n'
        break

with open('app.py', 'w') as f:
    f.writelines(lines)

print("Fixed import syntax")
