"""phzyx-plugin-hello — Diamond D9 example plugin package."""

from phzyx.plugin_hello.actions import hello_ping_action
from phzyx.plugin_hello.widgets import HelloBadgeWidget

__version__ = "0.1.0"
__all__ = ["HelloBadgeWidget", "hello_ping_action", "__version__"]
