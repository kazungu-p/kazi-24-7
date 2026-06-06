import re

with open('app.py', 'r') as f:
    content = f.read()

# Find the flask import line
if 'from flask import (' in content:
    # It's a multi-line import
    content = content.replace(
        'from flask import (',
        'from flask import (render_template_string,'
    )
else:
    # It's a single line import
    flask_import_match = re.search(r'from flask import ([^\(][^,]+(?:, [^,]+)*)', content)
    if flask_import_match:
        current_imports = flask_import_match.group(1)
        new_imports = 'render_template_string, ' + current_imports
        content = content.replace(
            f'from flask import {current_imports}',
            f'from flask import {new_imports}'
        )

with open('app.py', 'w') as f:
    f.write(content)

print("Added render_template_string import to app.py")
