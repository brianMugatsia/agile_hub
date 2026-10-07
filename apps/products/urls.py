from django.urls import path

from .views import ProductCreateView, ProductListView

app_name = "products"

urlpatterns = [
    path("", ProductListView.as_view(), name="list"),
    path("create/", ProductCreateView.as_view(), name="create"),
]