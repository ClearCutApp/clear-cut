"""Token verification boundary: claims cannot bypass revocation or email checks."""

from typing import Any

import pytest
from firebase_admin import auth

from clearcut.adapters.gcp.firebase_identity import FirebaseIdentityVerifier
from clearcut.domain.errors import SourceUnavailable
from clearcut.domain.identity import AuthenticationRequired


def claims(**overrides: Any) -> dict[str, Any]:
    return {
        "uid": "user-one",
        "email": "user@example.com",
        "email_verified": True,
        "firebase": {"sign_in_provider": "password"},
        **overrides,
    }


def test_verifier_requests_revocation_check_and_passes_project_bound_app():
    application = object()

    def verify(token, *, app, check_revoked):
        assert token == "signed-token"
        assert app is application
        assert check_revoked is True
        return claims()

    identity = FirebaseIdentityVerifier(application, verify).verify("signed-token")
    assert identity.user_id == "user-one"


@pytest.mark.parametrize(
    "payload",
    [
        claims(email_verified=False),
        claims(uid=""),
        claims(firebase={"sign_in_provider": "anonymous"}),
        claims(email=""),
    ],
)
def test_unverified_or_unsupported_accounts_are_refused(payload):
    with pytest.raises(AuthenticationRequired):
        FirebaseIdentityVerifier(None, lambda *args, **kwargs: payload).verify("token")


def test_certificate_outage_is_unavailable_not_a_bad_login():
    def verify(*args, **kwargs):
        raise auth.CertificateFetchError("private network details")

    with pytest.raises(SourceUnavailable, match="identity service unavailable"):
        FirebaseIdentityVerifier(None, verify).verify("token")


def test_revoked_token_is_refused():
    def verify(*args, **kwargs):
        raise auth.RevokedIdTokenError("revoked")

    with pytest.raises(AuthenticationRequired):
        FirebaseIdentityVerifier(None, verify).verify("token")
