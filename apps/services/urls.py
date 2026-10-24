from django.urls import path

from . import views

app_name = "services"

urlpatterns = [
    # Service Bookings (Ripening batches, Machine hire)
    path("bookings/", views.ServiceBookingListView.as_view(), name="booking_list"),
    path("bookings/new/", views.ServiceBookingCreateView.as_view(), name="booking_create"),
    path("bookings/export/<str:format>/", views.BookingExportView.as_view(), name="booking_export"),
    path("bookings/<uuid:pk>/", views.ServiceBookingDetailView.as_view(), name="booking_detail"),
    path("bookings/<uuid:pk>/edit/", views.ServiceBookingUpdateView.as_view(), name="booking_edit"),
    path("bookings/<uuid:pk>/action/", views.ServiceBookingActionView.as_view(), name="booking_action"),

    # Hub Resources (Equipment, Ripening Chambers, Harvesters)
    path("resources/", views.HubResourceListView.as_view(), name="resource_list"),
    path("resources/new/", views.HubResourceCreateView.as_view(), name="resource_create"),
    path("resources/export/<str:format>/", views.ResourceExportView.as_view(), name="resource_export"),
    path("resources/<uuid:pk>/", views.HubResourceDetailView.as_view(), name="resource_detail"),
    path("resources/<uuid:pk>/edit/", views.HubResourceUpdateView.as_view(), name="resource_edit"),

    # Service Types (Catalog)
    path("catalog/", views.ServiceTypeListView.as_view(), name="service_type_list"),
    path("catalog/new/", views.ServiceTypeCreateView.as_view(), name="service_type_create"),
    path("catalog/export/<str:format>/", views.ServiceTypeExportView.as_view(), name="service_type_export"),
    path("catalog/<int:pk>/", views.ServiceTypeDetailView.as_view(), name="service_type_detail"),
    path("catalog/<int:pk>/edit/", views.ServiceTypeUpdateView.as_view(), name="service_type_edit"),

    # Service Providers (Internal & External)
    path("providers/", views.ServiceProviderListView.as_view(), name="provider_list"),
    path("providers/internal/", views.InternalServiceProviderListView.as_view(), name="internal_provider_list"),
    path("providers/external/", views.ExternalServiceProviderListView.as_view(), name="external_provider_list"),
    path("providers/new/", views.ServiceProviderCreateView.as_view(), name="provider_create"),
    path("providers/export/<str:format>/", views.ProviderExportView.as_view(), name="provider_export"),
    path("providers/<uuid:pk>/", views.ServiceProviderDetailView.as_view(), name="provider_detail"),
    path("providers/<uuid:pk>/edit/", views.ServiceProviderUpdateView.as_view(), name="provider_edit"),
    path("providers/<uuid:pk>/action/", views.ServiceProviderActionView.as_view(), name="provider_action"),
]
