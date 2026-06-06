import sys

with open('app.py', 'r') as f:
    lines = f.readlines()

# Check indentation level
for i, line in enumerate(lines):
    stripped = line.lstrip()
    if stripped:
        indent = len(line) - len(stripped)
        # Check for inconsistent indentation
        if i > 0 and stripped and not stripped.startswith('#'):
            prev_indent = len(lines[i-1]) - len(lines[i-1].lstrip())
            if abs(indent - prev_indent) > 4 and prev_indent % 4 == 0 and indent % 4 != 0:
                print(f"Line {i+1}: Possible indentation issue")
                print(f"  Previous indent: {prev_indent}, Current: {indent}")
                print(f"  Line: {repr(line)}")
