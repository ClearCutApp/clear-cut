"""Firebase identity tokens, with revocation and verified email enforcement."""

from collections.abc import Callable
from typing import Any

from firebase_admin import auth

from clearcut.domain.errors import SourceUnavailable
from clearcut.domain.identity import AuthenticationRequired, Identity


class FirebaseIdentityVerifier:
    def __init__(self, app: Any, verify_token: Callable[..., Any] = auth.verify_id_token) -> None:
        self._app = app
        self._verify_token = verify_token

    def verify(self, token: str) -> Identity:
        try:
            claims = self._verify_token(token, app=self._app, check_revoked=True)
        except auth.CertificateFetchError as exc:
            raise SourceUnavailable("identity service unavailable") from exc
        except (
            auth.InvalidIdTokenError,
            auth.RevokedIdTokenError,
            auth.UserDisabledError,
            ValueError,
        ) as exc:
            raise AuthenticationRequired("sign in again") from exc
        except Exception as exc:
            raise SourceUnavailable("identity service unavailable") from exc
        provider = claims.get("firebase", {}).get("sign_in_provider")
        if (
            claims.get("email_verified") is not True
            or provider not in {"google.com", "password"}
            or not claims.get("uid")
            or not claims.get("email")
        ):
            raise AuthenticationRequired("a verified Google or email account is required")
        return Identity(str(claims["uid"]), str(claims["email"]))
