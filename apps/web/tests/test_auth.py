from __future__ import annotations

from apps.web.streamlit_app.utils.jwt_utils import decode_jwt_payload, extract_user_claims
from apps.web.streamlit_app.view_models.auth import build_current_user_view_model


def _sample_token() -> str:
    import base64
    import json

    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
    payload = base64.urlsafe_b64encode(
        json.dumps(
            {
                "sub": "user-1",
                "username": "analyst",
                "role": "analyst",
                "auth_method": "jwt",
                "exp": 9999999999,
            }
        ).encode()
    ).decode().rstrip("=")
    return f"{header}.{payload}.signature"


def test_decode_jwt_payload_extracts_role() -> None:
    payload = decode_jwt_payload(_sample_token())
    assert payload["username"] == "analyst"
    assert payload["role"] == "analyst"


def test_extract_user_claims_maps_fields() -> None:
    claims = extract_user_claims(_sample_token())
    assert claims["user_id"] == "user-1"
    assert claims["role"] == "analyst"


def test_build_current_user_view_model_for_api_key_auth() -> None:
    vm = build_current_user_view_model(
        {"auth_mode": "api_key", "username": "viewer", "role": "viewer", "user_id": "viewer"}
    )
    assert vm.auth_method == "api_key"
    assert vm.role == "viewer"
