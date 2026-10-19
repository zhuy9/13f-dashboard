import pytest
import security_master


@pytest.fixture(autouse=True)
def _no_security_master_network(monkeypatch):
    """No network or local data in tests: a test that reaches security-master without faking it
    fails here instead of downloading the dataset, or reading a cached copy, and passing locally."""

    def refuse():
        raise AssertionError("test reached security-master; fake enrich.sm instead")

    monkeypatch.setattr(security_master, "_current", refuse)
