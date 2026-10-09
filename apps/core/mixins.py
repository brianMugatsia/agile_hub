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


class ActiveHubInitialMixin:
    """Pre-fills the hub field of a create form with the hub chosen in the top bar."""

    hub_initial_field = "hub"

    def get_initial(self):
        initial = super().get_initial()
        from apps.hubs.permissions import selected_hub

        _hubs, hub, _error = selected_hub(self.request)
        if hub is not None:
            initial.setdefault(self.hub_initial_field, hub.pk)
        return initial