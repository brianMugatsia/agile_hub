import calendar
import re
import time
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.accounts.roles import Role
from apps.beneficiaries.models import BeneficiaryProfile, Business
from apps.hubs.models import Hub, HubMembership
from apps.inventory.models import InventoryBalance, InventoryTransaction
from apps.inventory.services import record_movement
from apps.payroll.models import SalaryRecord, WorkerProfile
from apps.products.models import Product
from apps.sales.models import Sale
from apps.sales.services import complete_sale


class Command(BaseCommand):
    help = "Create deterministic sample records in a development or demo database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sales",
            type=int,
            default=100,
            help="Target number of demo sales for this batch (0 to 10000; default: 100).",
        )
        parser.add_argument(
            "--batch",
            default="sample",
            help="Short alphanumeric batch label. Re-running the same batch is idempotent.",
        )

    def handle(self, *args, **options):
        settings_module = getattr(settings, "SETTINGS_MODULE", "")
        if settings_module == "config.settings.production":
            raise CommandError(
                "Sample seeding is disabled under production settings."
            )
        if not getattr(settings, "DEMO_DATA_ENABLED", False):
            raise CommandError(
                "Sample seeding is disabled for this database. Use development or demo settings."
            )

        sales_target = options["sales"]
        batch = options["batch"]
        if not 0 <= sales_target <= 10_000:
            raise CommandError("--sales must be between 0 and 10000.")
        if not re.fullmatch(r"[A-Za-z0-9-]{1,24}", batch):
            raise CommandError("--batch must be 1-24 letters, numbers, or hyphens.")

        started = time.perf_counter()
        User = get_user_model()
        agent, created = User.objects.get_or_create(
            username="agilehub-demo-agent",
            defaults={
                "email": "agilehub-demo-agent@example.invalid",
                "first_name": "Demo",
                "last_name": "Agent",
                "role": Role.SALES_AGENT,
            },
        )
        if created:
            agent.set_unusable_password()
            agent.save(update_fields=["password"])
        elif agent.role != Role.SALES_AGENT:
            raise CommandError("The reserved agilehub-demo-agent account exists with another role.")

        hub, _ = Hub.objects.get_or_create(
            code="DEMO-NAIROBI",
            defaults={
                "name": "Demo Nairobi Hub",
                "region": "Nairobi",
                "address": "Sample data only",
            },
        )
        HubMembership.objects.get_or_create(
            hub=hub, user=agent, defaults={"title": "Demo Sales Agent"}
        )

        beneficiary_specs = (
            ("agilehub-demo-beneficiary-1", "Wanjiku", "Farmers Cooperative", "Agriculture", "0700000101"),
            ("agilehub-demo-beneficiary-2", "Otieno", "Green Basket Produce", "Fresh produce", "0700000102"),
            ("agilehub-demo-beneficiary-3", "Njeri", "Sunrise Poultry Group", "Poultry", "0700000103"),
        )
        for number, (username, last_name, business_name, business_type, phone_number) in enumerate(
            beneficiary_specs, start=1
        ):
            beneficiary_user, user_created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"{username}@example.invalid",
                    "first_name": ("Demo", "Sample", "Community")[number - 1],
                    "last_name": last_name,
                    "role": Role.BENEFICIARY,
                },
            )
            if user_created:
                beneficiary_user.set_unusable_password()
                beneficiary_user.save(update_fields=["password"])
            elif beneficiary_user.role != Role.BENEFICIARY:
                raise CommandError(f"The reserved {username} account exists with another role.")

            beneficiary, _ = BeneficiaryProfile.objects.get_or_create(
                user=beneficiary_user,
                defaults={
                    "phone_number": phone_number,
                    "address": "Nairobi County",
                    "hub": hub,
                    "notes": "Sample beneficiary profile; fictional demo data.",
                },
            )
            business, _ = Business.objects.get_or_create(
                beneficiary=beneficiary,
                name=f"Demo {business_name}",
                defaults={
                    "hub": hub,
                    "business_type": business_type,
                    "registration_number": f"DEMO-BIZ-{number:03d}",
                    "phone_number": phone_number,
                    "address": "Nairobi County",
                    "status": Business.Status.ACTIVE,
                },
            )

        product_specs = (
            ("DEMO-OIL", "Demo Sunflower Oil", "Oil", "Litre", "620.00", "430.00"),
            ("DEMO-FEED", "Demo Poultry Feed", "Feeds", "Bag", "1850.00", "1420.00"),
            ("DEMO-FERT", "Demo Fertilizer", "Farm inputs", "Bag", "2400.00", "1950.00"),
        )
        products = []
        for sku, name, category, unit, price, cost in product_specs:
            product, _ = Product.objects.get_or_create(
                sku=sku,
                defaults={
                    "name": name,
                    "category": category,
                    "unit": unit,
                    "selling_price": price,
                    "cost_price": cost,
                    "reorder_level": 5,
                },
            )
            products.append(product)

        references = [f"DEMO-{batch}-{number:06d}" for number in range(1, sales_target + 1)]
        existing = set(
            Sale.objects.filter(hub=hub, payment_reference__in=references).values_list(
                "payment_reference", flat=True
            )
        )
        pending_numbers = [
            number for number, reference in enumerate(references, start=1) if reference not in existing
        ]

        pending_per_product = [0] * len(products)
        for number in pending_numbers:
            pending_per_product[(number - 1) % len(products)] += 1
        for product, needed in zip(products, pending_per_product):
            balance, _ = InventoryBalance.objects.get_or_create(hub=hub, product=product)
            shortage = max(0, needed - balance.quantity)
            if shortage:
                record_movement(
                    hub=hub,
                    product=product,
                    kind=InventoryTransaction.Kind.RECEIPT,
                    quantity=shortage,
                    actor=agent,
                    unit_cost=product.cost_price,
                    reference=f"demo-stock-{batch}",
                    notes="Generated demo inventory; not a physical stock count.",
                )

        for number in pending_numbers:
            product = products[(number - 1) % len(products)]
            complete_sale(
                hub=hub,
                agent=agent,
                actor=agent,
                items=[{"product": product.pk, "quantity": 1}],
                customer_name=f"Demo Customer {number:06d}",
                payment_method=Sale.PaymentMethod.CASH,
                payment_reference=f"DEMO-{batch}-{number:06d}",
                notes="Generated demo transaction.",
            )

        today = timezone.localdate()
        period_start = today.replace(day=1)
        period_end = today.replace(day=calendar.monthrange(today.year, today.month)[1])
        worker_specs = (
            ("agilehub-demo-worker-1", "DEMO-EMP-001", "Amina", "Mwangi", "Field Officer", "42000.00"),
            ("agilehub-demo-worker-2", "DEMO-EMP-002", "Peter", "Otieno", "Stock Coordinator", "36000.00"),
            ("agilehub-demo-worker-3", "DEMO-EMP-003", "Grace", "Wanjiku", "Community Liaison", "39000.00"),
        )
        for number, (username, employee_code, first_name, last_name, title, salary_amount) in enumerate(
            worker_specs, start=1
        ):
            worker_user, user_created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"{username}@example.invalid",
                    "first_name": first_name,
                    "last_name": last_name,
                    "role": Role.WORKER,
                },
            )
            if user_created:
                worker_user.set_unusable_password()
                worker_user.save(update_fields=["password"])
            elif worker_user.role != Role.WORKER:
                raise CommandError(f"The reserved {username} account exists with another role.")

            worker, _ = WorkerProfile.objects.get_or_create(
                user=worker_user,
                defaults={
                    "hub": hub,
                    "employee_code": employee_code,
                    "job_title": title,
                    "monthly_salary": Decimal(salary_amount),
                    "hired_on": period_start.replace(year=max(period_start.year - 1, 2000)),
                },
            )
            if worker.employee_code != employee_code:
                raise CommandError(f"The reserved {username} account has a different worker profile.")

            SalaryRecord.objects.get_or_create(
                worker=worker,
                period_start=period_start,
                period_end=period_end,
                defaults={
                    "gross_amount": Decimal(salary_amount),
                    "deductions": Decimal("0.00"),
                    "status": SalaryRecord.Status.PENDING,
                    "notes": f"Sample payroll record {number}; not a real employee payment.",
                },
            )

        elapsed = time.perf_counter() - started
        created_count = len(pending_numbers)
        self.stdout.write(
            self.style.SUCCESS(
                f"Demo batch '{batch}' is ready: {sales_target} target sales, "
                f"{created_count} created, {sales_target - created_count} already present "
                f"in database '{settings.DATABASES['default']['NAME']}'. "
                f"Includes {len(worker_specs)} sample workers and current-month pending salary records. "
                f"Includes {len(beneficiary_specs)} beneficiaries and businesses. "
                f"Elapsed: {elapsed:.2f}s."
            )
        )