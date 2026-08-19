"""Editors come from Authentik; their groups decide what they may do.

No local passwords: the account is created on first login from the claims, and
its Django groups mirror the Authentik ones on every login, so revoking access
upstream takes effect immediately.
"""

from django.conf import settings
from django.contrib.auth.models import Group
from mozilla_django_oidc.auth import OIDCAuthenticationBackend


class AuthentikBackend(OIDCAuthenticationBackend):
    def verify_claims(self, claims):
        """Membership of the editing group is the gate; everyone else is refused
        before an account is even created."""
        return settings.OIDC_EDITOR_GROUP in self._groups(claims)

    def create_user(self, claims):
        return self._sync(super().create_user(claims), claims)

    def update_user(self, user, claims):
        return self._sync(user, claims)

    def _sync(self, user, claims):
        groups = self._groups(claims)
        user.first_name = claims.get("given_name", "")[:150]
        user.last_name = claims.get("family_name", "")[:150]
        user.email = claims.get("email", "")
        # `is_staff` opens the admin and /edition/; it follows the group, so
        # losing it upstream closes the door at the next login.
        user.is_staff = settings.OIDC_EDITOR_GROUP in groups
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


def may_publish(user):
    return user.is_superuser or user.groups.filter(name=settings.OIDC_PUBLISHER_GROUP).exists()
