"""Execute arbitrary Python code in the sandbox."""

import json
import os
import sys
import io
import traceback

params = json.loads(os.environ.get("PARVA_PARAMS", "{}"))
code = params.get("code", "")

if not code:
    print(json.dumps({"error": "No code provided"}))
    sys.exit(0)

# Capture stdout
old_stdout = sys.stdout
sys.stdout = captured = io.StringIO()

result = None
error = None

try:
    # Execute the code
    exec_globals = {"__builtins__": __builtins__}
    exec(code, exec_globals)
    # Check if there's a 'result' variable set by the code
    if "result" in exec_globals:
        result = exec_globals["result"]
except Exception as e:
    error = traceback.format_exc()

output = captured.getvalue()
sys.stdout = old_stdout

response = {
    "output": output,
    "result": result if result is not None else output,
}
if error:
    response["error"] = error

print(json.dumps(response, default=str))
