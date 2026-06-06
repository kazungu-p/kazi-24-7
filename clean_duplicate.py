with open('app.py', 'r') as f:
    lines = f.readlines()

# Find and remove duplicate @app.route('/test-minimal')
found_first = False
new_lines = []
skip_next = False

for i, line in enumerate(lines):
    if '@app.route(\'/test-minimal\')' in line or '@app.route("/test-minimal")' in line:
        if not found_first:
            found_first = True
            new_lines.append(line)
            # Also include the function definition that follows
        else:
            # This is the duplicate - skip this route and its function
            skip_next = True
            continue
    elif skip_next:
        if line.strip() == '' or line.startswith(' ') or line.startswith('\t'):
            continue
        else:
            skip_next = False
            new_lines.append(line)
    else:
        new_lines.append(line)

# Write back
with open('app.py', 'w') as f:
    f.writelines(new_lines)

print("Cleaned duplicate route!")
