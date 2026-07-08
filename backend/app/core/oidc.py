"""Helpers for direct Google OpenID Connect authentication."""

from __future__ import annotations

import base64
import hashlib
import secrets
from functools import lru_cache
from urllib.parse import urlencode, urlparse

import httpx
from authlib.jose import JsonWebKey, jwt

from app.core.config import settings


@lru_cache(maxsize=1)
def discovery_url() -> str:
    if not settings.oidc_issuer:
        raise RuntimeError("OIDC_ISSUER is not configured")
    return settings.oidc_issuer.rstrip("/") + "/.well-known/openid-configuration"


def _require_https_endpoint(discovery: dict, name: str) -> str:
    value = discovery.get(name)
    if not isinstance(value, str) or urlparse(value).scheme != "https":
        raise ValueError(f"OIDC discovery contains invalid {name}")
    return value


async def get_discovery() -> dict:
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
        response = await client.get(discovery_url())
        response.raise_for_status()
        discovery = response.json()

    configured_issuer = (settings.oidc_issuer or "").rstrip("/")
    discovered_issuer = str(discovery.get("issuer") or "").rstrip("/")
    if not configured_issuer or discovered_issuer != configured_issuer:
        raise ValueError("OIDC discovery issuer mismatch")

    _require_https_endpoint(discovery, "authorization_endpoint")
    _require_https_endpoint(discovery, "token_endpoint")
    _require_https_endpoint(discovery, "jwks_uri")
    return discovery


def code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def build_authorization_url(
    discovery: dict,
    redirect_uri: str,
    state: str,
    nonce: str,
    code_verifier: str,
) -> str:
    query = urlencode(
        {
            "client_id": settings.oidc_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge(code_verifier),
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
    )
    return f"{_require_https_endpoint(discovery, 'authorization_endpoint')}?{query}"


async def exchange_code(discovery: dict, code: str, redirect_uri: str, code_verifier: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
        response = await client.post(
            _require_https_endpoint(discovery, "token_endpoint"),
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": settings.oidc_client_id,
                "client_secret": settings.oidc_client_secret,
                "code_verifier": code_verifier,
            },
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        return response.json()


async def validate_id_token(discovery: dict, id_token: str, nonce: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
        jwks_response = await client.get(_require_https_endpoint(discovery, "jwks_uri"))
        jwks_response.raise_for_status()
    key_set = JsonWebKey.import_key_set(jwks_response.json())
    claims = jwt.decode(id_token, key_set)
    claims.validate()

    configured_issuer = (settings.oidc_issuer or "").rstrip("/")
    token_issuer = str(claims.get("iss") or "").rstrip("/")
    if not configured_issuer or token_issuer != configured_issuer:
        raise ValueError("Invalid issuer")

    expected_audience = settings.oidc_audience or settings.oidc_client_id
    if not expected_audience:
        raise RuntimeError("OIDC audience is not configured")

    aud = claims.get("aud")
    if isinstance(aud, str):
        audiences = [aud]
    elif isinstance(aud, list) and all(isinstance(item, str) for item in aud):
        audiences = aud
    else:
        raise ValueError("Invalid audience claim")

    if expected_audience not in audiences:
        raise ValueError("Invalid audience")
    if len(audiences) > 1 and claims.get("azp") != expected_audience:
        raise ValueError("Invalid authorized party")

    token_nonce = claims.get("nonce")
    if not isinstance(token_nonce, str) or not secrets.compare_digest(token_nonce, nonce):
        raise ValueError("Invalid nonce")
    return dict(claims)
