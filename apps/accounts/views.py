from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.functional import cached_property
from django.views.generic import DetailView, FormView, ListView, UpdateView

from apps.core.mixins import PageMixin

from . import services
from .forms import (
    LoginForm,
    ProfileForm,
    RoleAssignForm,
    StyledPasswordChangeForm,
    StyledPasswordResetForm,
    StyledSetPasswordForm,
    UserCreateForm,
    UserUpdateForm,
)
from .models import User
from .permissions import can_manage_user
from .roles import Role, assignable_roles
from .selectors import users_visible_to


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
class LoginView(auth_views.LoginView):
    template_name = "registration/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class PasswordChangeView(PageMixin, SuccessMessageMixin, auth_views.PasswordChangeView):
    template_name = "registration/password_change_form.html"
    form_class = StyledPasswordChangeForm
    success_url = reverse_lazy("accounts:profile")
    success_message = "Your password was changed."
    page_title = "Change password"
    breadcrumbs = (("My profile", reverse_lazy("accounts:profile")), ("Change password", None))


class PasswordResetView(auth_views.PasswordResetView):
    template_name = "registration/password_reset_form.html"
    form_class = StyledPasswordResetForm
    email_template_name = "registration/password_reset_email.html"
    subject_template_name = "registration/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")


class PasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "registration/password_reset_done.html"


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "registration/password_reset_confirm.html"
    form_class = StyledSetPasswordForm
    success_url = reverse_lazy("accounts:password_reset_complete")


class PasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "registration/password_reset_complete.html"


# ---------------------------------------------------------------------------
# Own profile
# ---------------------------------------------------------------------------
class ProfileView(LoginRequiredMixin, PageMixin, SuccessMessageMixin, UpdateView):
    form_class = ProfileForm
    template_name = "accounts/profile.html"
    context_object_name = "profile_user"  # "user" would shadow the signed-in user in templates
    success_url = reverse_lazy("accounts:profile")
    success_message = "Your profile was updated."
    page_title = "My profile"

    def get_object(self, queryset=None):
        return User.objects.get(pk=self.request.user.pk)


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------
class UserListView(PermissionRequiredMixin, PageMixin, ListView):
    permission_required = "accounts.view_user"
    template_name = "accounts/user_list.html"
    context_object_name = "users"
    paginate_by = 15
    page_title = "Users"
    breadcrumbs = (("Users", None),)

    def get_queryset(self):
        queryset = users_visible_to(self.request.user)
        query = self.request.GET.get("q", "").strip()
        role = self.request.GET.get("role", "")
        status = self.request.GET.get("status", "")
        if query:
            queryset = queryset.filter(
                Q(username__icontains=query)
                | Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(email__icontains=query)
                | Q(phone_number__icontains=query)
            )
        if role in Role.values:
            queryset = queryset.filter(role=role)
        if status == "active":
            queryset = queryset.filter(is_active=True)
        elif status == "inactive":
            queryset = queryset.filter(is_active=False)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["role_choices"] = Role.choices
        context["filters"] = {
            "q": self.request.GET.get("q", "").strip(),
            "role": self.request.GET.get("role", ""),
            "status": self.request.GET.get("status", ""),
        }
        return context


class UserDetailView(PermissionRequiredMixin, PageMixin, DetailView):
    permission_required = "accounts.view_user"
    template_name = "accounts/user_detail.html"
    context_object_name = "profile_user"

    def get_queryset(self):
        # Users outside the actor's scope are a 404, so IDs cannot be probed.
        return users_visible_to(self.request.user)

    def get_page_title(self):
        return self.object.display_name

    def get_breadcrumbs(self):
        return [("Users", reverse("accounts:user_list")), (self.object.display_name, None)]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        actor = self.request.user
        manageable = can_manage_user(actor, self.object)
        context["can_edit"] = manageable and actor.has_perm("accounts.change_user")
        context["can_assign_role"] = (
            manageable and actor.has_perm("accounts.assign_roles") and bool(assignable_roles(actor))
        )
        return context


class UserCreateView(PermissionRequiredMixin, PageMixin, FormView):
    permission_required = "accounts.add_user"
    form_class = UserCreateForm
    template_name = "accounts/user_form.html"
    page_title = "New user"
    breadcrumbs = (("Users", reverse_lazy("accounts:user_list")), ("New user", None))

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["actor"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["submit_label"] = "Create user"
        context["multipart"] = False
        return context

    def form_valid(self, form):
        user = services.create_user_from_form(form, actor=self.request.user, request=self.request)
        messages.success(self.request, f"{user.display_name} was created as {user.get_role_display()}.")
        return redirect("accounts:user_detail", pk=user.pk)


class UserUpdateView(PermissionRequiredMixin, PageMixin, UpdateView):
    permission_required = "accounts.change_user"
    form_class = UserUpdateForm
    template_name = "accounts/user_form.html"
    context_object_name = "profile_user"

    def get_queryset(self):
        return users_visible_to(self.request.user)

    def get_object(self, queryset=None):
        user = super().get_object(queryset)
        if not can_manage_user(self.request.user, user):
            raise PermissionDenied
        return user

    def get_page_title(self):
        return f"Edit {self.object.display_name}"

    def get_breadcrumbs(self):
        return [
            ("Users", reverse("accounts:user_list")),
            (self.object.display_name, reverse("accounts:user_detail", args=[self.object.pk])),
            ("Edit", None),
        ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["submit_label"] = "Save changes"
        context["multipart"] = True
        return context

    def form_valid(self, form):
        user = services.update_user_from_form(form, actor=self.request.user, request=self.request)
        messages.success(self.request, f"{user.display_name} was updated.")
        return redirect("accounts:user_detail", pk=user.pk)


class UserRoleView(PermissionRequiredMixin, PageMixin, FormView):
    permission_required = "accounts.assign_roles"
    form_class = RoleAssignForm
    template_name = "accounts/assign_role.html"

    @cached_property
    def target(self):
        user = get_object_or_404(users_visible_to(self.request.user), pk=self.kwargs["pk"])
        if not can_manage_user(self.request.user, user):
            raise PermissionDenied
        return user

    def get_page_title(self):
        return f"Change role: {self.target.display_name}"

    def get_breadcrumbs(self):
        return [
            ("Users", reverse("accounts:user_list")),
            (self.target.display_name, reverse("accounts:user_detail", args=[self.target.pk])),
            ("Change role", None),
        ]

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(actor=self.request.user, current_role=self.target.role)
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["target"] = self.target
        return context

    def form_valid(self, form):
        try:
            services.change_user_role(
                user=self.target,
                new_role=form.cleaned_data["role"],
                actor=self.request.user,
                request=self.request,
            )
        except ValidationError as error:
            form.add_error(None, error)
            return self.form_invalid(form)
        messages.success(
            self.request,
            f"{self.target.display_name} is now {self.target.get_role_display()}.",
        )
        return redirect("accounts:user_detail", pk=self.target.pk)