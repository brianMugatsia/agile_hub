from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.views.generic import CreateView
from django.views.generic import ListView

from apps.hubs.permissions import hubs_for_user

from .mixins import PageMixin
from .scoping import scope_queryset
from apps.audit.services import record_event


class ScopedModelListView(LoginRequiredMixin, PermissionRequiredMixin, PageMixin, ListView):
    """Permission-checked, paginated list with role-aware row scoping."""

    template_name = "components/record_list.html"
    paginate_by = 25
    columns = ()
    search_fields = ()
    create_url_name = ""
    create_label = "Add record"
    create_permission = ""

    def get_permission_required(self):
        if self.permission_required:
            return super().get_permission_required()
        return (f"{self.model._meta.app_label}.view_{self.model._meta.model_name}",)

    def get_queryset(self):
        return self._search(scope_queryset(super().get_queryset(), self.request.user))

    def _search(self, queryset):
        query = self.request.GET.get("q", "").strip()
        if query and self.search_fields:
            condition = Q()
            for field in self.search_fields:
                condition |= Q(**{f"{field}__icontains": query})
            queryset = queryset.filter(condition)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            page_title=self.page_title,
            breadcrumbs=self.get_breadcrumbs(),
            columns=self.columns,
            create_url_name=self.create_url_name,
            create_label=self.create_label,
            search_query=self.request.GET.get("q", ""),
            search_fields=self.search_fields,
            can_create=bool(
                self.create_url_name
                and self.create_permission
                and self.request.user.has_perm(self.create_permission)
            ),
        )
        return context


class ProtectedCreateView(LoginRequiredMixin, PermissionRequiredMixin, PageMixin, CreateView):
    template_name = "components/record_form.html"
    success_url_name = ""
    submit_label = "Save"

    def get_permission_required(self):
        if self.permission_required:
            return super().get_permission_required()
        return (f"{self.model._meta.app_label}.add_{self.model._meta.model_name}",)

    @transaction.atomic
    def form_valid(self, form):
        if any(field.name == "created_by" for field in self.model._meta.fields):
            form.instance.created_by = self.request.user
        response = super().form_valid(form)
        record_event(
            action=f"{self.model._meta.app_label}.{self.model._meta.model_name}.created",
            summary=f"Created {self.model._meta.verbose_name}: {form.instance}",
            actor=self.request.user,
            target=form.instance,
            request=self.request,
        )
        return response

    def get_success_url(self):
        return reverse(self.success_url_name)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            page_title=self.page_title,
            breadcrumbs=self.get_breadcrumbs(),
            submit_label=self.submit_label,
        )
        return context
