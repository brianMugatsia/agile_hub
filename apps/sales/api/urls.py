from django.urls import path, include

from .views import CompleteSaleView, router

urlpatterns = [
    path("complete/", CompleteSaleView.as_view(), name="complete-sale"),
    path("", include(router.urls)),
]