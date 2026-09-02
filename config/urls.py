import re

from django.conf import settings
from django.urls import include, path, re_path
from django.views.static import serve

from accueil import views


urlpatterns = [
    path("", views.index, name="index"),
    path("api/cities", views.cities, name="cities"),
    path("search", views.search, name="search"),
]

if settings.LOCAL_UPLOADS_ENABLED:
    # Only meaningful for the local-disk fallback: an S3 bucket serves its own
    # uploads directly, and this route is otherwise never mounted, so a
    # production deploy never serves MEDIA_ROOT off its own ephemeral disk.
    # Built by hand rather than `django.conf.urls.static.static`, which is
    # also a no-op outside DEBUG — a distinct condition from this one.
    urlpatterns += [
        re_path(
            rf"^{re.escape(settings.MEDIA_URL.lstrip('/'))}(?P<path>.*)$",
            serve,
            kwargs={"document_root": settings.MEDIA_ROOT},
        ),
    ]

# The editing UI and the admin are only routable when there is a way to sign in.
# Mounting the editor without one gave a 500 rather than a login: the redirect
# had nowhere to point.
if settings.ADMIN_ENABLED:
    from django.contrib import admin

    urlpatterns += [
        path("edition/", include("config.urls_edition")),
        path("admin/logout/", views.logout_url, name="logout"),
        path("admin/", admin.site.urls),
    ]
