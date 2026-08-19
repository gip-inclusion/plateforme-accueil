"""The public page is framed on purpose; the back-office never is.

The site-wide CSP deliberately allows `*.inclusion.gouv.fr` and, historically,
`*.cleverapps.io` / `*.scalingo.io` to embed the showcase page. Anyone can host
on those last two, so leaving the admin under the same policy would make it
clickjackable. `/edition/` denies framing per view, but the Django admin is not
ours to decorate — hence this, by path.
"""

BACK_OFFICE = ("/admin/", "/edition/")


class BackOfficeIsNeverFramed:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith(BACK_OFFICE):
            response.headers["X-Frame-Options"] = "DENY"
            # Read by ContentSecurityPolicyMiddleware, which runs later in the
            # response phase because it is listed before this one.
            response._csp_config = {"frame-ancestors": ["'none'"]}
        return response
