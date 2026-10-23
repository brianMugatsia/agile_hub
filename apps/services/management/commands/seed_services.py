from decimal import Decimal
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.hubs.models import Hub
from apps.members.models import MemberProfile
from apps.services.models import (
    ServiceType,
    HubResource,
    ServiceProvider,
    ServiceBooking,
    ServiceCategory,
    ServicePricingUnit,
    ProviderType,
    ServiceProviderStatus,
)
from apps.services.services import (
    create_service_booking,
    start_service_booking,
    complete_service_booking,
    record_booking_payment,
    register_service_provider,
)
from apps.commissions.models import ServiceCommission
from apps.commissions.services import (
    accrue_service_commission,
    approve_service_commission,
    pay_service_commission,
)
from apps.finance.models import FinancialSetting
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Seed the database with a realistic service catalogue, hub resources, service providers, and service bookings."

    def handle(self, *args, **options):
        self.stdout.write("Seeding service catalogue, resources, providers, and bookings...")
        User = get_user_model()
        admin = User.objects.filter(is_superuser=True).first()

        FinancialSetting.objects.get_or_create(
            effective_from=timezone.localdate() - timedelta(days=60),
            defaults={
                "default_commission_rate": Decimal("0.20"),
                "internal_commission_rate": Decimal("0.20"),
                "external_commission_rate": Decimal("0.22"),
                "default_sales_expense_rate": Decimal("0.05"),
                "provider_dormancy_days": Decimal("90.00"),
                "is_active": True,
                "created_by": admin,
            },
        )

        services_data = [
            ("RIP-BANANA", "Banana Ripening Chamber Service", ServiceCategory.RIPENING, ServicePricingUnit.PER_KG, Decimal("15.00"), "Controlled ethylene gas ripening for export-grade bananas."),
            ("HARV-MAIZE", "Combine Harvester Hire", ServiceCategory.HARVESTING, ServicePricingUnit.PER_ACRE, Decimal("2500.00"), "High-efficiency combine harvester with operator for maize & wheat."),
            ("MILL-GRAIN", "Commercial Grain Milling & Grading", ServiceCategory.PROCESSING, ServicePricingUnit.PER_KG, Decimal("3.50"), "Professional milling, sorting, and packaging of grains."),
            ("COLD-STR", "Cold & Dry Storage Facility", ServiceCategory.STORAGE, ServicePricingUnit.PER_DAY, Decimal("200.00"), "Temperature-controlled cold storage for perishable horticulture produce."),
            ("TRANS-LOG", "Bulk Produce Haulage & Transport", ServiceCategory.TRANSPORT, ServicePricingUnit.PER_DAY, Decimal("12000.00"), "Heavy-duty truck transport for farm-to-hub and market delivery."),
        ]

        services = []
        for code, name, cat, unit, rate, desc in services_data:
            srv, _ = ServiceType.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "category": cat,
                    "pricing_unit": unit,
                    "standard_rate": rate,
                    "description": desc,
                    "is_active": True,
                },
            )
            services.append(srv)

        hubs = list(Hub.objects.all())
        if not hubs:
            self.stdout.write(self.style.ERROR("No hubs found. Please run seed_demo_data first."))
            return

        resources = []
        for hub in hubs:
            for srv in services:
                res, _ = HubResource.objects.get_or_create(
                    hub=hub,
                    code=f"{hub.code}-{srv.code[:3]}-01",
                    defaults={
                        "service_type": srv,
                        "name": f"{hub.name} {srv.name}",
                        "capacity": Decimal("5000.00") if srv.category == ServiceCategory.STORAGE else Decimal("100.00"),
                        "capacity_unit": "kg" if srv.pricing_unit == ServicePricingUnit.PER_KG else "units",
                        "status": HubResource.Status.AVAILABLE,
                        "operator_name": f"Operator for {hub.name}",
                        "hourly_or_daily_cost": Decimal("1500.00"),
                    },
                )
                resources.append(res)

        providers = []
        members = list(MemberProfile.objects.all())
        for i in range(1, 4):
            member = members[i-1] if i <= len(members) else None
            prov = register_service_provider(
                provider_type=ProviderType.INTERNAL,
                name=f"Internal Partner {i} ({member.user.display_name if member else 'Member'})",
                member=member,
                phone_number=f"07123456{i:02d}",
                email=f"provider{i}@agilehub.local",
                address="Hub Partner Zone",
                service_category=ServiceCategory.HARVESTING,
                actor=admin,
            )
            providers.append(prov)

        for j in range(1, 3):
            prov = register_service_provider(
                provider_type=ProviderType.EXTERNAL,
                name=f"External Specialist Contractor {j}",
                member=None,
                phone_number=f"07234567{j:02d}",
                email=f"external{j}@contractor.local",
                address="Nairobi Regional Logistics",
                service_category=ServiceCategory.TRANSPORT,
                actor=admin,
            )
            providers.append(prov)

        for hub in hubs:
            hub_resources = [r for r in resources if r.hub_id == hub.pk]
            for b_idx in range(5):
                res = hub_resources[b_idx % len(hub_resources)]
                srv = res.service_type
                prov = providers[b_idx % len(providers)]
                start = timezone.now() - timedelta(days=b_idx + 1)
                end = start + timedelta(days=1)

                try:
                    booking = create_service_booking(
                        hub=hub,
                        resource=res,
                        service_type=srv,
                        service_provider=prov,
                        start_date=start,
                        end_date=end,
                        quantity=Decimal("150.00"),
                        unit_rate=srv.standard_rate,
                        customer_name=f"Client Farmer {b_idx + 1} ({hub.region})",
                        customer_phone=f"07889900{b_idx:02d}",
                        notes=f"Realistic seeded service engagement #{b_idx+1}",
                        actor=admin,
                    )
                    start_service_booking(booking_id=booking.pk, actor=admin)
                    complete_service_booking(booking_id=booking.pk, actor=admin, actual_quantity=Decimal("150.00"), notes="Successfully processed.")
                    record_booking_payment(booking_id=booking.pk, payment_reference=f"PAY-SRV-{hub.code}-{b_idx+1}", actor=admin)

                    comm = accrue_service_commission(booking)
                    if comm:
                        approve_service_commission(commission_id=comm.pk, actor=admin)
                        pay_service_commission(commission_id=comm.pk, actor=admin, payment_reference=f"COMM-PAY-{comm.pk}")
                except Exception as e:
                    pass

        self.stdout.write(self.style.SUCCESS("Successfully seeded rich service catalogue, resources, providers, and service bookings!"))
