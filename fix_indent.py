with open('app.py', 'r') as f:
    lines = f.readlines()

# Find the debug-check endpoint
for i, line in enumerate(lines):
    if '@app.route(\'/debug-check\')' in line or '@app.route("/debug-check")' in line:
        print(f"Found debug-check at line {i+1}:")
        # Print next 15 lines
        for j in range(i, min(i+15, len(lines))):
            print(f"{j+1}: {repr(lines[j])}")
        break
