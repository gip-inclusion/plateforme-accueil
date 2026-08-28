"""Editors come from Authentik; their groups decide what they may do.

No local passwords: the account is created on first login from the claims, and
its rights are recomputed from the claims on every login. Losing the group
upstream therefore *downgrades* the account rather than refusing the login —
refusing it would leave `is_staff` untouched from the previous session, which is
the opposite of what revocation should do.
"""

from django.contrib.auth.hashers import make_password
from mozilla_django_oidc.auth import OIDCAuthenticationBackend


class AuthentikBackend(OIDCAuthenticationBackend):
    def create_user(self, claims):
        return self.create_or_update(claims)

    def update_user(self, user, claims):
        return self.create_or_update(claims)

    def create_or_update(self, claims):
        defaults = {
            "first_name": claims.get("given_name", "")[:150],
            "last_name": claims.get("usual_name", "")[:150],
            "username": self.get_username(claims),
        }
        create_defaults = defaults | {
            "password": make_password(None),
            "is_staff": False,
            "is_superuser": False,
        }

        user, _created = self.UserModel.objects.update_or_create(
            email=claims.get("email", ""),
            defaults=defaults,
            create_defaults=create_defaults,
        )
        return user
