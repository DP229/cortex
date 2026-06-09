"""One-shot newline-collapse repair for cortex/ibm_elm/agent_tools.py."""
from pathlib import Path

p = Path("cortex/ibm_elm/agent_tools.py")
text = p.read_text(encoding="utf-8")

fixes = [
    # 1. docstring-end collapsed onto try:
    ('"""    try:\n', '"""\n    try:\n'),
    # 2. _disabled_result() collapsed onto validation_errors
    (
        "return _disabled_result()        validation_errors = elm_cfg.validate()",
        "return _disabled_result()\n\n        validation_errors = elm_cfg.validate()",
    ),
    # 3. closing paren collapsed onto services = ...
    (
        ")            services = discoverer.discover_all()",
        ")\n            services = discoverer.discover_all()",
    ),
    # 4. registry.register(tool)  collapsed onto if tools:
    (
        "        registry.register(tool)    if tools:",
        "        registry.register(tool)\n    if tools:",
    ),
]

count = 0
for old, new in fixes:
    if old in text:
        text = text.replace(old, new)
        count += 1
        print(f"  fixed: {old[:60]!r}")
    else:
        print(f"  miss : {old[:60]!r}")

p.write_text(text, encoding="utf-8")
print(f"Applied {count}/{len(fixes)} fixes")
