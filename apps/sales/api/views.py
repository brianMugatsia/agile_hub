from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.routers import DefaultRouter

from apps.core.api.resources import register_readonly, serializer_for
from apps.sales.models import Sale, SaleItem
from apps.sales.services import complete_sale

from .serializers import CompleteSaleSerializer


class CompleteSaleView(APIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = CompleteSaleSerializer

    def post(self, request):
        if not request.user.has_perm("sales.add_sale"):
            raise PermissionDenied
        serializer = CompleteSaleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            sale = complete_sale(
                hub=data["hub"],
                agent=request.user,
                items=[{"product": data["product"].pk, "quantity": data["quantity"]}],
                actor=request.user,
                customer_name=data.get("customer_name", ""),
                customer_phone=data.get("customer_phone", ""),
                payment_method=data["payment_method"],
                payment_reference=data.get("payment_reference", ""),
                notes=data.get("notes", ""),
                business=data.get("business"),
            )
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.message_dict if hasattr(error, "message_dict") else error.messages)
        result = serializer_for(Sale)(sale).data
        return Response(result, status=status.HTTP_201_CREATED)


router = DefaultRouter()
register_readonly(router, Sale, "sales", "sale")
register_readonly(router, SaleItem, "items", "sale-item")