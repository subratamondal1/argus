from __future__ import annotations

import argus


def test_version_is_exposed() -> None:
    assert isinstance(argus.__version__, str)
    assert argus.__version__
