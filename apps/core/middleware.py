from django.utils.cache import add_never_cache_headers


class NoStoreForAuthenticatedMiddleware:
    """Stops browsers caching signed-in pages (back button must not reveal financial data)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            add_never_cache_headers(response)
        return response