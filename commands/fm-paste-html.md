---
description: (Renamed) Now /fm-implement — see commands/fm-implement.md
---

The `/fm-paste-html` command was renamed to **`/fm-implement`** to better
reflect its broader role: building paste-ready implementation packages for
FileMaker scripts, layouts, and schema changes — not just HTML pages of
scripts.

**See [`commands/fm-implement.md`](./fm-implement.md) for the current docs.**

The `paste-html` and `paste` subcommands of `fm_manage.py` continue to work
as aliases for `implement`, so anything that already calls the old name
will keep working. If you typed `/fm-paste-html`, use `/fm-implement`
instead — same behaviour, broader scope.
