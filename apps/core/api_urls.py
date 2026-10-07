from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView

urlpatterns = [
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("accounts/", include("apps.accounts.api.urls")),
    path("hubs/", include("apps.hubs.api.urls")),
    path("beneficiaries/", include("apps.beneficiaries.api.urls")),
    path("products/", include("apps.products.api.urls")),
    path("inventory/", include("apps.inventory.api.urls")),
    path("sales/", include("apps.sales.api.urls")),
    path("commissions/", include("apps.commissions.api.urls")),
    path("payroll/", include("apps.payroll.api.urls")),
    path("finance/", include("apps.finance.api.urls")),
    path("audit/", include("apps.audit.api.urls")),
    path("notifications/", include("apps.notifications.api.urls")),
]