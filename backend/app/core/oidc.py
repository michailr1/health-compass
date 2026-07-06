"""OIDC helper functions for Authentik integration."""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache
from urllib.parse import urlencode

import httpx
from authlib.jose import JsonWebKey, jwt

from app.core.config import settings


@lru_cache(maxsize=1)
def discovery_url() -> str:
    if not settings.oidc_issuer:
        raise RuntimeError("OIDC_ISSUER is not configured")
    return settings.oidc_issuer.rstrip("/") + "/.well-known/openid-configuration"


async def get_discovery() -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(discovery_url())
        response.raise_for_status()
        return response.json()


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
        }
    )
    return f"{discovery['authorization_endpoint']}?{query}"


async def exchange_code(discovery: dict, code: str, redirect_uri: str, code_verifier: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            discovery["token_endpoint"],
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
    async with httpx.AsyncClient(timeout=10.0) as client:
        jwks_response = await client.get(discovery["jwks_uri"])
        jwks_response.raise_for_status()
    key_set = JsonWebKey.import_key_set(jwks_response.json())
    claims = jwt.decode(id_token, key_set)
    claims.validate()
    if claims.get("iss") != settings.oidc_issuer:
        raise ValueError("Invalid issuer")
    expected_audience = settings.oidc_audience or settings.oidc_client_id
    aud = claims.get("aud")
    if isinstance(aud, str):
        valid_audience = aud == expected_audience
    else:
        valid_audience = expected_audience in (aud or [])
    if not valid_audience:
        raise ValueError("Invalid audience")
    if claims.get("nonce") != nonce:
        raise ValueError("Invalid nonce")
    return dict(claims)
