from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model


class EmailOrUsernameModelBackend(ModelBackend):
    """Allows authentication using either username or email address."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(get_user_model().USERNAME_FIELD)
        if username is None:
            return None

        user_model = get_user_model()
        user = None
        try:
            if "@" in username:
                user = user_model.objects.get(email__iexact=username)
            else:
                user = user_model.objects.get(username__exact=username)
        except user_model.DoesNotExist:
            user_model().set_password(password)
        else:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        return None
