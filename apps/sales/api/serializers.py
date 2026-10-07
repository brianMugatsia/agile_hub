from rest_framework import serializers

from apps.hubs.models import Hub
from apps.products.models import Product
from apps.beneficiaries.models import Business


class CompleteSaleSerializer(serializers.Serializer):
    hub = serializers.PrimaryKeyRelatedField(queryset=Hub.objects.filter(status=Hub.Status.ACTIVE))
    business = serializers.PrimaryKeyRelatedField(
        queryset=Business.objects.filter(status=Business.Status.ACTIVE), required=False, allow_null=True
    )
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.filter(is_active=True))
    quantity = serializers.IntegerField(min_value=1)
    customer_name = serializers.CharField(max_length=160, required=False, allow_blank=True)
    customer_phone = serializers.CharField(max_length=24, required=False, allow_blank=True)
    payment_method = serializers.ChoiceField(
        choices=("CASH", "MOBILE_MONEY", "BANK", "CREDIT"), default="CASH"
    )
    payment_reference = serializers.CharField(max_length=80, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)