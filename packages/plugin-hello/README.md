# phzyx-plugin-hello

Diamond **D9** example plugin package demonstrating AdminBoard entry points.

## Entry points

| Group | Name | Target |
|-------|------|--------|
| `phzyx.admin.widgets` | `hello_badge` | `HelloBadgeWidget` |
| `phzyx.admin.actions` | `hello_ping` | `hello_ping_action` |

## Install (workspace)

```bash
uv add phzyx-plugin-hello
```

Discover:

```python
from importlib.metadata import entry_points
eps = entry_points(group="phzyx.admin.widgets")
print(list(eps))
```
