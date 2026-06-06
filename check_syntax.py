import sys
try:
    with open('app.py', 'r') as f:
        code = f.read()
    # Try to compile it
    compile(code, 'app.py', 'exec')
    print("✅ Syntax is valid")
except SyntaxError as e:
    print(f"❌ Syntax error: {e}")
    # Show the problematic line
    lines = code.split('\n')
    if e.lineno:
        print(f"Error at line {e.lineno}:")
        print(f"  {lines[e.lineno-1]}")
