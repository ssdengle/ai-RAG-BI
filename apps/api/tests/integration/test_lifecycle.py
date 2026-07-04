from fastapi.testclient import TestClient

from apps.api.app.main import create_app
from apps.api.tests.conftest import FakeDatabaseManager, FakeRedisManager


def test_application_startup_initializes_infrastructure(test_settings) -> None:
    database_manager = FakeDatabaseManager()
    redis_manager = FakeRedisManager()
    app = create_app(
        settings=test_settings,
        database_manager=database_manager,
        redis_manager=redis_manager,
        perform_startup_checks=True,
    )

    with TestClient(app):
        pass

    assert database_manager.initialize_calls == [True]
    assert redis_manager.initialize_calls == [True]


def test_application_shutdown_releases_infrastructure(test_settings) -> None:
    database_manager = FakeDatabaseManager()
    redis_manager = FakeRedisManager()
    app = create_app(
        settings=test_settings,
        database_manager=database_manager,
        redis_manager=redis_manager,
        perform_startup_checks=False,
    )

    with TestClient(app):
        pass

    assert database_manager.disposed is True
    assert redis_manager.closed is True
