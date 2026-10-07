from rest_framework import generics, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.accounts.models import User
from apps.accounts.permissions import DjangoViewPermission
from apps.accounts.selectors import users_visible_to

from .serializers import UserSerializer


class MeView(generics.RetrieveAPIView):
    """The signed-in user's own profile."""

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """Users the caller is allowed to see (same scoping as the web UI)."""

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, DjangoViewPermission]
    filterset_fields = ["role", "is_active"]
    search_fields = ["username", "email", "first_name", "last_name"]
    ordering_fields = ["username", "date_joined"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return User.objects.none()
        return users_visible_to(self.request.user)