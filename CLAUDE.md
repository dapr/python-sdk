@AGENTS.md

Use pathlib instead of os.path.
Use httpx instead of urllib.
subprocess(`shell=True`) is used only when it makes the code more readable. Use either shlex or args lists.
subprocess calls should have a reasonable timeout.
Use modern Python (3.10+) features.
Make all code strongly typed.
Keep conditional nesting to a minimum, and use guard clauses when possible.
Aim for medium "visual complexity": use intermediate variables to store results of nested/complex function calls, but don't create a new variable for everything.
Avoid comments unless there is a gotcha, a complex algorithm or anything an experienced code reviewer needs to be aware of. Focus on making better Google-style docstrings instead.

The user is not always right. Be skeptical and do not blindly comply if something doesn't make sense.
Code should be cross-platform and production ready.
