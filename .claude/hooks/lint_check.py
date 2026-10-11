"""PostToolUse hook: enforce one-line docstrings and naming on edited Python files."""
import ast
import re
import shutil
import subprocess
import sys

from _common import read_event

SNAKE = re.compile(r"^_{0,2}[a-z][a-z0-9_]*_{0,2}$")
PASCAL = re.compile(r"^_?[A-Z][A-Za-z0-9]*$")


def check_source(source):
    """Return a list of docstring and naming violations found in source."""
    problems = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not SNAKE.match(node.name):
                problems.append(f"line {node.lineno}: function '{node.name}' must be snake_case")
        elif isinstance(node, ast.ClassDef):
            if not PASCAL.match(node.name):
                problems.append(f"line {node.lineno}: class '{node.name}' must be PascalCase")
        else:
            continue
        doc = ast.get_docstring(node, clean=True)
        if not doc:
            problems.append(f"line {node.lineno}: '{node.name}' needs a one-line docstring")
        elif "\n" in doc.strip():
            problems.append(f"line {node.lineno}: '{node.name}' docstring must be a single line")
    return problems


def run_ruff(path):
    """Run ruff on path when installed; return its output or an empty string."""
    if not shutil.which("ruff"):
        return ""
    result = subprocess.run(["ruff", "check", "--quiet", path], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode else ""


def main():
    """Lint the edited .py file and report issues back to Claude via stderr."""
    event = read_event()
    path = event.get("tool_input", {}).get("file_path", "")
    if not path.endswith(".py"):
        sys.exit(0)
    try:
        with open(path, encoding="utf-8") as handle:
            problems = check_source(handle.read())
    except (OSError, SyntaxError) as err:
        problems = [f"could not parse: {err}"]
    ruff_out = run_ruff(path)
    if ruff_out:
        problems.append(ruff_out)
    if problems:
        print(f"Style issues in {path}:\n" + "\n".join(problems), file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
