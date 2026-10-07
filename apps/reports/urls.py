from django.urls import path

from .views import ReportIndexView

app_name = "reports"

urlpatterns = [path("", ReportIndexView.as_view(), name="index")]