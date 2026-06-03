"""Shared pytest fixtures."""
import pytest
from django.contrib.auth import get_user_model


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(
        username="tester", password="pw", email="tester@example.com"
    )


@pytest.fixture
def auth_client(client, user):
    """A Django test client already logged in as ``user``."""
    client.force_login(user)
    return client
