"""Disposable Firebase account proves signed-token and disabled-user boundaries.

Email delivery itself is not established by this test; a browser verification
journey remains required. No email is sent to the reserved synthetic address.
"""

import secrets
import uuid

import firebase_admin
import httpx
import pytest
from firebase_admin import auth

from clearcut.adapters.gcp.firebase_identity import FirebaseIdentityVerifier
from clearcut.domain.identity import AuthenticationRequired
from tests.live.conftest import env, requires


@pytest.mark.live
@requires("GOOGLE_CLOUD_PROJECT", "FIREBASE_WEB_API_KEY")
def test_live_firebase_token_is_project_verified_and_disabled_user_is_refused() -> None:
    suffix = uuid.uuid4().hex
    application = firebase_admin.initialize_app(
        options={"projectId": env("GOOGLE_CLOUD_PROJECT"), "httpTimeout": 15},
        name="clearcut-live-" + suffix,
    )
    uid = "clearcut-test-" + suffix
    email = uid + "@example.invalid"
    password = secrets.token_urlsafe(32)
    created = False
    try:
        user = auth.create_user(
            uid=uid, email=email, password=password, email_verified=True, app=application
        )
        created = True
        assert user.uid == uid
        response = httpx.post(
            "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
            params={"key": env("FIREBASE_WEB_API_KEY")},
            json={"email": email, "password": password, "returnSecureToken": True},
            timeout=20,
        )
        assert response.status_code == 200, "Firebase password sign-in did not succeed"
        token = response.json()["idToken"]
        verifier = FirebaseIdentityVerifier(application)
        assert verifier.verify(token).user_id == uid
        auth.update_user(uid, disabled=True, app=application)
        with pytest.raises(AuthenticationRequired):
            verifier.verify(token)
    finally:
        if created:
            auth.delete_user(uid, app=application)
        firebase_admin.delete_app(application)
