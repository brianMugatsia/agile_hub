import json
from urllib.parse import urlencode

from django.apps import apps
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

from .models import SavedFilter


FILTER_KEYS = {
    "q", "role", "status", "start", "end", "kind", "direction", "hub",
}


def _return_url(request):
    target = request.POST.get("return_to", "")
    if not target or not url_has_allowed_host_and_scheme(
        target,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return reverse("core:dashboard")
    return target


class SaveFilterView(LoginRequiredMixin, View):
    def post(self, request):
        model_key = request.POST.get("model_key", "").lower()
        try:
            app_label, model_name = model_key.split(".", 1)
            model = apps.get_model(app_label, model_name)
        except (ValueError, LookupError):
            return HttpResponseBadRequest("Unknown list.")
        if not model or not request.user.has_perm(f"{app_label}.view_{model_name}"):
            return HttpResponseBadRequest("You cannot save filters for this list.")

        name = request.POST.get("name", "").strip()
        if not name or len(name) > 80:
            messages.error(request, "Enter a filter name of 1 to 80 characters.")
            return redirect(_return_url(request))
        try:
            raw_params = json.loads(request.POST.get("query_params", "{}"))
        except (TypeError, json.JSONDecodeError):
            messages.error(request, "The filter could not be saved.")
            return redirect(_return_url(request))
        if not isinstance(raw_params, dict):
            messages.error(request, "The filter could not be saved.")
            return redirect(_return_url(request))
        params = {}
        for key, value in raw_params.items():
            if key not in FILTER_KEYS:
                continue
            values = value if isinstance(value, list) else [value]
            values = [item[:120] for item in values if isinstance(item, str) and item]
            if values:
                params[key] = values

        SavedFilter.objects.create(
            model_key=f"{app_label}.{model_name}",
            name=name,
            query_params=params,
            created_by=request.user,
        )
        messages.success(request, f"Shared filter “{name}” was saved.")
        return redirect(_return_url(request))


class DeleteFilterView(LoginRequiredMixin, View):
    def post(self, request, pk):
        saved_filter = get_object_or_404(SavedFilter, pk=pk, created_by=request.user)
        target = _return_url(request)
        saved_filter.delete()
        messages.success(request, "Shared filter was removed.")
        return redirect(target)
