@AGENTS.md

Make all code strongly typed.
Keep conditional nesting to a minimum, and use guard clauses when possible.
Aim for medium visual complexity: use intermediate variables to store results of nested/complex function calls. A complex function call could be:
- `f(Object(a=1, b=2, c=3))`, the inner object has more than 2 meaningful args
- `f(Object((a, b)))`, 2 levels of nesting or anything with a long chain of closing parens
- `small_transformation(ImportantObject())`, the object itself is the main subject of the function but the transformation steals the focus
Use descriptive, self-documenting names for these intermediate variables.
Closely related variable names should share a root and use different suffixes. For example, `request_original` and `request_clean`, but not `clean_request`.
Avoid comments unless there is a gotcha, a complex algorithm or anything an experienced code reviewer needs to be aware of. Focus on making short but descriptive Google-style docstrings instead.

Use modern Python (3.10+) features.
Use pathlib instead of os.path.
Use httpx instead of urllib.
`subprocess(shell=True)` is used only when it makes the code more readable. Use either shlex or args lists.
Anything that can have an explicit timeout should have one.
Code should be cross-platform and production ready.

The user is not always right. Be skeptical and do not blindly comply if something doesn't make sense.
