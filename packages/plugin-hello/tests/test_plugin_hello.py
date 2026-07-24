from __future__ import annotations

import pytest
from phzyx.plugin_hello import HelloBadgeWidget, hello_ping_action


@pytest.mark.unit
def test_widget_serialize() -> None:
    w = HelloBadgeWidget()
    assert "hi" in w.serialize("hi")


@pytest.mark.unit
def test_action_descriptor() -> None:
    a = hello_ping_action()
    assert a["name"] == "hello_ping"
    assert a["scope"] == "global"
