from functools import lru_cache

from rest_framework import serializers, viewsets

from apps.accounts.permissions import DjangoViewPermission

from apps.core.scoping import scope_queryset


@lru_cache
def serializer_for(model):
    meta = type("Meta", (), {"model": model, "fields": "__all__"})
    return type(f"{model.__name__}ReadSerializer", (serializers.ModelSerializer,), {"Meta": meta})


class ScopedReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (DjangoViewPermission,)
    model = None

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.model._default_manager.none()
        queryset = self.model._default_manager.all()
        return scope_queryset(queryset, self.request.user)

    def get_serializer_class(self):
        return serializer_for(self.model)


def register_readonly(router, model, route, basename):
    viewset = type(
        f"{model.__name__}ReadOnlyViewSet",
        (ScopedReadOnlyViewSet,),
        {"model": model, "__module__": __name__},
    )
    router.register(route, viewset, basename=basename)
