from pathlib import Path

from app.api.deps import get_conn
from app.main import app

REPO = Path(__file__).resolve().parents[2]


def _routes(routes):
    for route in routes:
        if hasattr(route, "original_router"):  # FastAPI wraps included routers
            yield from _routes(route.original_router.routes)
        else:
            yield route


def _dependants(dependant):
    for dep in dependant.dependencies:
        yield dep
        yield from _dependants(dep)


def test_db_transaction_commits_before_response_is_sent():
    """With the default 'request' scope FastAPI runs the commit after the response is sent."""
    found = 0
    for route in _routes(app.routes):
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        for dep in _dependants(dependant):
            if dep.call is get_conn:
                found += 1
                assert dep.scope == "function", f"{route.path} uses get_conn with scope {dep.scope!r}"
    assert found > 0


def test_compose_does_not_default_to_trusting_dev_auth():
    compose = (REPO / "docker-compose.yml").read_text()
    assert "${APP_ENV:-dev}" not in compose
    assert "${APP_ENV:-prod}" in compose
    assert "change-me" not in compose
