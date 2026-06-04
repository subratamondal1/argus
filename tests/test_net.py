from __future__ import annotations

import pytest

from argus.net import UnsafeUrlError, assert_safe_url


def test_public_address_is_allowed() -> None:
    assert_safe_url("https://8.8.8.8/")  # a public IP literal — no DNS, no network


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://localhost:8000/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/internal",
        "http://192.168.1.1/",
        "http://[::1]/",
    ],
)
def test_internal_addresses_are_refused(url: str) -> None:
    with pytest.raises(UnsafeUrlError):
        assert_safe_url(url)


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://host/x", "gopher://h/"])
def test_non_http_schemes_are_refused(url: str) -> None:
    with pytest.raises(UnsafeUrlError):
        assert_safe_url(url)
