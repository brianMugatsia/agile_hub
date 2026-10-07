from .forms import HubForm
from .models import Hub
from apps.core.generic import ProtectedCreateView, ScopedModelListView, hubs_for_user


class HubListView(ScopedModelListView):
    model = Hub
    page_title = "Hubs"
    columns = (
        {"label": "Code", "field": "code"},
        {"label": "Hub", "field": "name"},
        {"label": "Region", "field": "region"},
        {"label": "Manager", "field": "manager__display_name"},
        {"label": "Status", "field": "status"},
    )
    search_fields = ("code", "name", "region")
    create_url_name = "hubs:create"
    create_permission = "hubs.add_hub"


class HubCreateView(ProtectedCreateView):
    model = Hub
    form_class = HubForm
    page_title = "Create hub"
    success_url_name = "hubs:list"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if self.request.user.role not in ("SUPER_ADMIN", "ADMIN"):
            form.fields["manager"].queryset = form.fields["manager"].queryset.filter(
                hub_memberships__hub__in=hubs_for_user(self.request.user)
            ).distinct()
        return form