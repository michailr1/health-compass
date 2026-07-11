"""Route table integrity tests.

Every method/path pair must have exactly one owner so that behavior can never
depend on ``include_router`` registration order (HC-015 Slice A / CR-01).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from fastapi.routing import APIRoute

from app.main import app

REVIEW_MODULE = "app.api.routes.clinical_review"
CONTEXT_MODULE = "app.api.routes.clinical_context"


def _iter_api_routes(routes: Iterable[object], prefix: str = "") -> Iterator[tuple[str, APIRoute]]:
    """Yield (full_path, route) for every concrete APIRoute.

    FastAPI ≥0.139 registers included routers lazily as ``_IncludedRouter``
    entries, so plain iteration over ``app.routes`` no longer sees the
    concrete routes; recurse through ``original_router`` (with its include
    prefix) to enumerate the effective route table.
    """
    for route in routes:
        if isinstance(route, APIRoute):
            yield prefix + route.path, route
            continue
        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            include_context = getattr(route, "include_context", None)
            child_prefix = prefix + getattr(include_context, "prefix", "")
            yield from _iter_api_routes(original_router.routes, child_prefix)


def _routes_by_key() -> dict[tuple[str, str], list[APIRoute]]:
    result: dict[tuple[str, str], list[APIRoute]] = {}
    for path, route in _iter_api_routes(app.routes):
        for method in sorted(route.methods or ()):
            if method == "HEAD":
                continue
            result.setdefault((method, path), []).append(route)
    return result


def test_no_duplicate_method_path_pairs() -> None:
    duplicates = {
        key: [route.endpoint.__module__ for route in routes]
        for key, routes in _routes_by_key().items()
        if len(routes) > 1
    }
    assert duplicates == {}, f"Duplicate route registrations found: {duplicates}"


def test_summary_and_review_routes_are_owned_by_clinical_review() -> None:
    routes = _routes_by_key()
    for key in (
        ("GET", "/profiles/{profile_id}/clinical-context"),
        ("GET", "/profiles/{profile_id}/clinical-context/state"),
        ("POST", "/profiles/{profile_id}/clinical-context/review"),
        ("PATCH", "/profiles/{profile_id}/clinical-context/sections/{section}/review"),
        ("POST", "/profiles/{profile_id}/conditions"),
        ("POST", "/profiles/{profile_id}/allergies"),
        ("POST", "/profiles/{profile_id}/medications"),
        ("POST", "/profiles/{profile_id}/supplements"),
    ):
        owners = [route.endpoint.__module__ for route in routes.get(key, [])]
        assert owners == [REVIEW_MODULE], f"{key}: expected single owner {REVIEW_MODULE}, got {owners}"


def test_record_routes_are_owned_by_clinical_context() -> None:
    routes = _routes_by_key()
    for section in ("conditions", "allergies", "medications", "supplements", "clinical-safety-flags"):
        for key in (
            ("GET", f"/profiles/{{profile_id}}/{section}"),
            ("PATCH", f"/profiles/{{profile_id}}/{section}/{{record_id}}"),
            ("POST", f"/profiles/{{profile_id}}/{section}/{{record_id}}/void"),
        ):
            owners = [route.endpoint.__module__ for route in routes.get(key, [])]
            assert owners == [CONTEXT_MODULE], f"{key}: expected single owner {CONTEXT_MODULE}, got {owners}"
    safety_create = [
        route.endpoint.__module__
        for route in routes.get(("POST", "/profiles/{profile_id}/clinical-safety-flags"), [])
    ]
    assert safety_create == [CONTEXT_MODULE]
