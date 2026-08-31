import urllib.parse

from django.contrib.auth import logout
from django.http import JsonResponse
from django.shortcuts import redirect, render

from accueil import cities as city_lookup, content, platform_urls
from accueil.sections.hero import Hero


def index(request):
    return render(
        request,
        "accueil/index.html",
        {
            "sections": content.page_sections(),
            # `/?type=insertion` lands straight on one search. Resolved
            # server-side, so it works with no JavaScript.
            "selected_search": Hero.resolve_search(request.GET.get("type", "")),
        },
    )


def cities(request):
    return JsonResponse(
        {"results": city_lookup.matches(request.GET.get("q", ""))},
        headers={"Access-Control-Allow-Origin": "*"},
    )


def login_view(request):
    return redirect("oidc_authentication_init")


def logout_url(request):
    # It would be better to logout from our sso but's it's not really an issue
    logout(request)
    return redirect("index")


def search(request):
    """Dispatch the hero's single search form to the right external site.

    The target is never built from the request: "type" is only ever a key into
    `Hero.searches`. Building a URL from it would be an open redirect.
    """
    requested_type = Hero.resolve_search(request.GET.get("type", ""))
    target = Hero.searches[requested_type]

    # The slug comes from the autocomplete; with no JavaScript none can be
    # produced, so the typed name is resolved here instead. Les emplois only
    # ever receives the slug it already understands.
    city = request.GET.get("city", "").strip()
    if not city:
        city = city_lookup.exact_slug(request.GET.get("city_name", ""))

    params = {}
    if city:
        params["city"] = city
    # The thematic filter only means anything for "insertion": dropped for the
    # other two, whether stale or tampered with.
    if requested_type == "insertion":
        category = request.GET.get("category", "").strip()
        if category:
            params["category"] = category

    url = platform_urls.url(request, target.results_path)
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    return redirect(url)
