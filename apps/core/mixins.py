class PageMixin:
    """Gives a view a page title and breadcrumbs for the base template."""

    page_title = ""
    breadcrumbs = ()  # tuples of (label, url_or_None)

    def get_page_title(self):
        return self.page_title

    def get_breadcrumbs(self):
        return list(self.breadcrumbs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("page_title", self.get_page_title())
        context.setdefault("breadcrumbs", self.get_breadcrumbs())
        return context