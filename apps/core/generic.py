import json
from datetime import date, datetime, time, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import FieldDoesNotExist
from django.db import models, transaction
from django.db.models import Q
from django.urls import reverse
from django.utils.http import urlencode
from django.utils import timezone
from django.views.generic import CreateView
from django.views.generic import ListView

from apps.hubs.permissions import hubs_for_user

from apps.audit.services import record_event
from .mixins import PageMixin
from .scoping import scope_queryset

from .models import SavedFilter


class ScopedModelListView(LoginRequiredMixin, PermissionRequiredMixin, PageMixin, ListView):
    """Permission-checked, paginated list with role-aware row scoping."""

    template_name = "components/record_list.html"
    paginate_by = 25
    columns = ()
    search_fields = ()
    create_url_name = ""
    create_label = "Add record"
    create_permission = ""
    export_url_name = ""
    import_url_name = ""
    import_permission = ""
    date_filter_field = ""
    filter_fields = ()
    filter_hub = False

    def get_permission_required(self):
        if self.permission_required:
            return super().get_permission_required()
        return (f"{self.model._meta.app_label}.view_{self.model._meta.model_name}",)

    def get_queryset(self):
        queryset = self._search(scope_queryset(super().get_queryset(), self.request.user))
        self.filter_error = ""
        start = self.request.GET.get("start", "")
        end = self.request.GET.get("end", "")
        if self.date_filter_field and (start or end):
            try:
                start_date = date.fromisoformat(start) if start else None
                end_date = date.fromisoformat(end) if end else None
                if start_date and start_date.isoformat() != start:
                    raise ValueError
                if end_date and end_date.isoformat() != end:
                    raise ValueError
                if start_date and end_date and end_date < start_date:
                    raise ValueError
                if start_date and end_date and (end_date - start_date).days + 1 > 366:
                    self.filter_error = "Choose a date range of no more than 366 days."
                elif start_date or end_date:
                    field = self.model._meta.get_field(self.date_filter_field)
                    if isinstance(field, models.DateTimeField):
                        if start_date:
                            start_at = timezone.make_aware(datetime.combine(start_date, time.min))
                            queryset = queryset.filter(**{f"{self.date_filter_field}__gte": start_at})
                        if end_date:
                            end_at = timezone.make_aware(datetime.combine(end_date + timedelta(days=1), time.min))
                            queryset = queryset.filter(**{f"{self.date_filter_field}__lt": end_at})
                    else:
                        if start_date:
                            queryset = queryset.filter(**{f"{self.date_filter_field}__gte": start_date})
                        if end_date:
                            queryset = queryset.filter(**{f"{self.date_filter_field}__lte": end_date})
            except (ValueError, TypeError):
                self.filter_error = "Enter valid dates and make sure the end date is not before the start date."
        for field_name, choices in self.filter_fields:
            selected = self.request.GET.get(field_name, "")
            if selected:
                if selected in dict(choices):
                    queryset = queryset.filter(**{field_name: selected})
                else:
                    self.filter_error = "Choose a valid filter option."
        if self.filter_hub:
            hub_id = self.request.GET.get("hub", "")
            hubs = hubs_for_user(self.request.user)
            if hub_id and hubs.filter(pk=hub_id).exists():
                queryset = queryset.filter(hub_id=hub_id)
            elif hub_id:
                self.filter_error = "Choose a hub you can access."
        if self.filter_error:
            queryset = queryset.none()
        related_fields = self._related_column_fields()
        return queryset.select_related(*related_fields) if related_fields else queryset

    def _related_column_fields(self):
        paths = set()
        for column in self.columns:
            model = self.model
            path = []
            for name in column.get("field", "").split("__"):
                try:
                    field = model._meta.get_field(name)
                except FieldDoesNotExist:
                    break
                if not (field.many_to_one or field.one_to_one) or field.related_model is None:
                    break
                path.append(name)
                model = field.related_model
            if path:
                paths.add("__".join(path))

        return tuple(
            path for path in sorted(paths)
            if not any(other.startswith(f"{path}__") for other in paths)
        )

    def _search(self, queryset):
        terms = self.request.GET.get("q", "").split()
        if terms and self.search_fields:
            for term in terms:
                condition = Q()
                for field in self.search_fields:
                    condition |= Q(**{f"{field}__icontains": term})
                queryset = queryset.filter(condition)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filter_key = f"{self.model._meta.app_label}.{self.model._meta.model_name}"
        filters = SavedFilter.objects.filter(model_key=filter_key).select_related("created_by")[:20]
        return_to = self.request.path
        filter_fields = [
            {
                "name": field_name,
                "choices": choices,
                "selected": self.request.GET.get(field_name, ""),
                "label": field_name.replace("_", " ").title(),
            }
            for field_name, choices in self.filter_fields
        ]
        hubs = hubs_for_user(self.request.user) if self.filter_hub else ()
        context.update(
            saved_filters=[
                {
                    "name": saved_filter.name,
                    "created_by": saved_filter.created_by,
                    "created_by_id": saved_filter.created_by_id,
                    "url": f"{return_to}?{urlencode(saved_filter.query_params, doseq=True)}",
                    "delete_url": reverse("core:saved_filter_delete", args=[saved_filter.pk]),
                    "id": saved_filter.pk,
                }
                for saved_filter in filters
            ],
            saved_filter_model_key=filter_key,
            saved_filter_return_to=return_to,
            saved_filter_query=json.dumps({
                key: self.request.GET.getlist(key)
                for key in self.request.GET
                if key != "page"
            }),
            export_url_name=self.export_url_name,
            import_url_name=self.import_url_name,
            can_import=bool(
                self.import_url_name
                and self.request.user.has_perm(self.import_permission)
            ),
            export_query=urlencode({
                key: value
                for key, value in self.request.GET.items()
                if key != "page"
            }),
            date_filter_field=self.date_filter_field,
            filter_start=self.request.GET.get("start", ""),
            filter_end=self.request.GET.get("end", ""),
            filter_error=getattr(self, "filter_error", ""),
            filter_fields=filter_fields,
            filter_hubs=hubs,
            selected_hub=self.request.GET.get("hub", ""),
        )
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
