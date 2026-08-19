"""Editors come from Authentik; their groups decide what they may do.

No local passwords: the account is created on first login from the claims, and
its rights are recomputed from the claims on every login. Losing the group
upstream therefore *downgrades* the account rather than refusing the login —
refusing it would leave `is_staff` untouched from the previous session, which is
the opposite of what revocation should do.
"""

from django.conf import settings
from django.contrib.auth.models import Group
from mozilla_django_oidc.auth import OIDCAuthenticationBackend


class AuthentikBackend(OIDCAuthenticationBackend):
    def create_user(self, claims):
        return self._sync(super().create_user(claims), claims)

    def update_user(self, user, claims):
        return self._sync(user, claims)

    def _sync(self, user, claims):
        groups = self._groups(claims)
        editor = settings.OIDC_EDITOR_GROUP in groups

        user.first_name = claims.get("given_name", "")[:150]
        user.last_name = claims.get("family_name", "")[:150]
        user.email = claims.get("email", "")
        # Follows the group, both ways: someone removed from it upstream loses
        # the admin and /edition/ at their next login.
        user.is_staff = editor
        # Never inherited. Accounts are matched on email, so without this an
        # Authentik user could land on a pre-existing local superuser row.
        user.is_superuser = False
        user.set_unusable_password()
        user.save()

        mirrored = [
            Group.objects.get_or_create(name=name)[0]
            for name in (settings.OIDC_EDITOR_GROUP, settings.OIDC_PUBLISHER_GROUP)
            if name in groups
        ]
        user.groups.set(mirrored)
        return user

    @staticmethod
    def _groups(claims):
        groups = claims.get("groups") or []
        return groups if isinstance(groups, list) else []
