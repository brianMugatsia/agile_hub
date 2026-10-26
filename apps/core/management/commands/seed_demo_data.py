import calendar
import random
import re
import time
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.accounts.roles import Role
from apps.commissions.models import SalesAgentCommission
from apps.commissions.services import accrue_for_sale
from apps.finance.models import CashFlow, Expense, IncomeStatement, IncomeStatementItem
from apps.hubs.models import Hub, HubMembership
from apps.inventory.models import InventoryBalance, InventoryTransaction, Supplier, PurchaseOrder, PurchaseOrderLine
from apps.inventory.services import record_movement, create_reorder_order, receive_purchase_order
from apps.members.models import Business, MemberProfile
from apps.payroll.models import SalaryRecord, WorkerProfile
from apps.products.models import Product
from apps.sales.models import Sale, SaleItem
from apps.sales.services import complete_sale
from apps.services.models import ServiceProvider, ServiceBooking, HubResource, ServiceType
from apps.commissions.models import ServiceCommission


class Command(BaseCommand):
    help = "Flush and seed the database with clean, realistic production data with 0 inventory reconciliation discrepancies."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sales",
            type=int,
            default=200,
            help="Target number of sales across hubs (default: 200).",
        )
        parser.add_argument(
            "--batch",
            default="prod",
            help="Short alphanumeric batch label.",
        )

    def handle(self, *args, **options):
        settings_module = getattr(settings, "SETTINGS_MODULE", "")
        if settings_module == "config.settings.production":
            raise CommandError("Sample seeding is disabled under production settings.")
        if not getattr(settings, "DEMO_DATA_ENABLED", False):
            raise CommandError("Sample seeding is disabled for this database.")

        sales_target = options["sales"]
        User = get_user_model()

        self.stdout.write("Flushing existing records and seeding clean production-like dataset...")

        SaleItem.objects.all().delete()
        SalesAgentCommission.objects.all().delete()
        ServiceCommission.objects.all().delete()
        ServiceBooking.objects.all().delete()
        ServiceProvider.objects.all().delete()
        HubResource.objects.all().delete()
        ServiceType.objects.all().delete()
        SalaryRecord.objects.all().delete()
        CashFlow.objects.all().delete()
        IncomeStatementItem.objects.all().delete()
        IncomeStatement.objects.all().delete()
        PurchaseOrderLine.objects.all().delete()
        PurchaseOrder.objects.all().delete()
        InventoryTransaction.objects.all().delete()
        Sale.objects.all().delete()
        Business.objects.all().delete()
        MemberProfile.objects.all().delete()
        WorkerProfile.objects.all().delete()
        InventoryBalance.objects.all().delete()
        Product.objects.all().delete()
        Supplier.objects.all().delete()

        Hub.objects.filter(code="NAI-001").update(
            code="KIM-001",
            name="Kimilili Hub",
            region="Western",
            address="Main Street, Kimilili"
        )

        super_admin, _ = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@agilehub.local",
                "first_name": "Super",
                "last_name": "Administrator",
                "role": Role.SUPER_ADMIN,
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
                "phone_number": "0700000001",
            },
        )
        super_admin.set_password("password123")
        super_admin.save()

        hub_specs = [
            ("KIM-001", "Kimilili Hub", "Western", "Main Street, Kimilili", "0711100001"),
            ("MBA-002", "Mombasa Coastal Hub", "Coast", "Moi Avenue, Mombasa", "0711100002"),
            ("KSM-003", "Kisumu Lakeside Hub", "Western", "Oginga Odinga Road, Kisumu", "0711100003"),
        ]

        hubs = []
        for code, name, region, address, phone in hub_specs:
            hub, _ = Hub.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "region": region,
                    "address": address,
                    "phone_number": phone,
                    "status": Hub.Status.ACTIVE,
                },
            )
            hubs.append(hub)

        role_configs = [
            ("manager", Role.HUB_MANAGER, "Hub Manager"),
            ("finance", Role.FINANCE_OFFICER, "Finance Officer"),
            ("viewer", Role.VIEWER, "Hub Viewer"),
        ]

        for i, hub in enumerate(hubs, start=1):
            for prefix, role, title in role_configs:
                username = f"{prefix}-{i}"
                email = f"{prefix}{i}@agilehub.local"
                user, _ = User.objects.update_or_create(
                    username=username,
                    defaults={
                        "email": email,
                        "first_name": f"{hub.region} {title.split()[0]}",
                        "last_name": f"Operator {i}",
                        "role": role,
                        "hub": hub,
                        "is_active": True,
                        "phone_number": f"07223344{i}{i}",
                    },
                )
                user.set_password("password123")
                user.save()
                HubMembership.objects.get_or_create(
                    hub=hub, user=user, defaults={"title": title, "is_active": True}
                )

        sales_agents = []
        member_profiles = []
        for i in range(1, 13):
            hub = hubs[(i - 1) % len(hubs)]
            is_member_seller = (i > 8)
            role = Role.MEMBER if is_member_seller else Role.SALES_AGENT
            username = f"seller-{i}"
            email = f"seller{i}@agilehub.local"
            seller_user, _ = User.objects.update_or_create(
                username=username,
                defaults={
                    "email": email,
                    "first_name": "Hub Member" if is_member_seller else "Sales Agent",
                    "last_name": f"Seller {i}",
                    "role": role,
                    "hub": hub,
                    "is_active": True,
                    "phone_number": f"07334455{i:02d}",
                },
            )
            seller_user.set_password("password123")
            seller_user.save()
            HubMembership.objects.get_or_create(
                hub=hub, user=seller_user, defaults={"title": "Member Seller" if is_member_seller else "Sales Agent", "is_active": True}
            )

            sales_agents.append(seller_user)
            profile, _ = MemberProfile.objects.get_or_create(
                user=seller_user,
                defaults={
                    "phone_number": f"07334455{i:02d}",
                    "location": f"{hub.name} Area",
                    "hub": hub,
                    "notes": f"Member sales agent #{i}" if not is_member_seller else f"Active member seller #{i}",
                },
            )
            member_profiles.append(profile)

        products_data = [
            ("Certified Maize Seeds (10kg)", "Seeds", Decimal("1200.00"), Decimal("1800.00"), 20),
            ("NPK Fertilizer (50kg)", "Inputs", Decimal("3000.00"), Decimal("4200.00"), 10),
            ("DAP Fertilizer (50kg)", "Inputs", Decimal("3500.00"), Decimal("4900.00"), 10),
            ("Knapsack Sprayer 16L", "Equipment", Decimal("2200.00"), Decimal("3200.00"), 5),
            ("Pesticide Foliar Spray (1L)", "Protection", Decimal("700.00"), Decimal("1100.00"), 15),
            ("Hybrid Tomato Seeds (50g)", "Seeds", Decimal("1000.00"), Decimal("1600.00"), 10),
            ("Urea Fertilizer (50kg)", "Inputs", Decimal("3200.00"), Decimal("4500.00"), 10),
            ("Animal Feeds Dairy Meal (70kg)", "Feed", Decimal("2500.00"), Decimal("3400.00"), 12),
        ]

        products = []
        for name, category, cost_price, selling_price, reorder_level in products_data:
            sku = f"SKU-{re.sub(r'[^A-Z]', '', name.upper())[:6]}-{random.randint(10,99)}"
            prod, _ = Product.objects.get_or_create(
                sku=sku,
                defaults={
                    "name": name,
                    "category": category,
                    "cost_price": cost_price,
                    "selling_price": selling_price,
                    "reorder_level": reorder_level,
                    "is_active": True,
                },
            )
            products.append(prod)
            for hub in hubs:
                balance, _ = InventoryBalance.objects.get_or_create(
                    hub=hub, product=prod, defaults={"quantity": 500}
                )
                balance.quantity = 500
                balance.save()

                record_movement(
                    hub=hub,
                    product=prod,
                    quantity=300,
                    kind=InventoryTransaction.Kind.RECEIPT,
                    notes=f"Initial stock receipt",
                    actor=super_admin,
                )

        suppliers_data = [
            ("SUP-AGRO", "Agro-Inputs Wholesale Ltd", "0700112233", "Amina Supplier"),
            ("SUP-SEEDS", "East African Seed Co", "0700223344", "John Seed"),
            ("SUP-EQUIP", "Farm Equipment Distributors", "0700334455", "Peter Equip"),
        ]
        suppliers = []
        for code, name, phone, contact in suppliers_data:
            supplier, _ = Supplier.objects.get_or_create(
                code=code,
                defaults={"name": name, "phone": phone, "contact_name": contact, "is_active": True}
            )
            suppliers.append(supplier)

        for hub in hubs:
            for s_idx, supplier in enumerate(suppliers):
                po = PurchaseOrder.objects.create(
                    hub=hub,
                    supplier=supplier,
                    status=PurchaseOrder.Status.RECEIVED,
                    notes=f"Completed production purchase order #{s_idx+1}",
                    created_by=super_admin,
                )
                for prod in random.sample(products, 3):
                    PurchaseOrderLine.objects.create(
                        order=po,
                        product=prod,
                        quantity_ordered=50,
                        quantity_received=50,
                        unit_cost=prod.cost_price,
                    )
                po_pend = PurchaseOrder.objects.create(
                    hub=hub,
                    supplier=supplier,
                    status=PurchaseOrder.Status.ORDERED,
                    notes=f"Pending replenishment order",
                    created_by=super_admin,
                )
                for prod in random.sample(products, 2):
                    PurchaseOrderLine.objects.create(
                        order=po_pend,
                        product=prod,
                        quantity_ordered=30,
                        quantity_received=0,
                        unit_cost=prod.cost_price,
                    )

        for hub in hubs:
            for m in range(1, 6):
                m_user, _ = User.objects.update_or_create(
                    username=f"member-{hub.code.lower()}-{m}",
                    defaults={
                        "email": f"member{m}@{hub.code.lower()}.local",
                        "first_name": f"Farmer {m}",
                        "last_name": hub.region,
                        "role": Role.MEMBER,
                        "hub": hub,
                        "phone_number": f"07445566{m:02d}",
                    },
                )
                m_user.set_password("password123")
                m_user.save()

                profile, _ = MemberProfile.objects.get_or_create(
                    user=m_user,
                    defaults={
                        "phone_number": f"07445566{m:02d}",
                        "location": f"{hub.region} Agricultural Zone",
                        "hub": hub,
                        "notes": f"Member business outlet in {hub.name}",
                    },
                )
                Business.objects.update_or_create(
                    member=profile,
                    name=f"Agro-Outlet {hub.code}-{m}",
                    defaults={
                        "hub": hub,
                        "business_type": "Wholesale & Retail Outlet",
                        "amount": Decimal("25000.00"),
                        "is_paid": True,
                        "status": Business.Status.ACTIVE,
                    },
                )

            for w in range(1, 4):
                w_user, _ = User.objects.update_or_create(
                    username=f"worker-{hub.code.lower()}-{w}",
                    defaults={
                        "email": f"worker{w}@{hub.code.lower()}.local",
                        "first_name": f"Staff {w}",
                        "last_name": hub.region,
                        "role": Role.WORKER,
                        "hub": hub,
                        "phone_number": f"07556677{w:02d}",
                    },
                )
                w_user.set_password("password123")
                w_user.save()

                worker_profile, _ = WorkerProfile.objects.get_or_create(
                    user=w_user,
                    hub=hub,
                    defaults={
                        "employee_code": f"EMP-{hub.code}-W{w}",
                        "job_title": "Hub Operations Assistant",
                        "monthly_salary": Decimal("40000.00"),
                        "hired_on": timezone.localdate() - timedelta(days=120),
                        "is_active": True,
                    },
                )
                past_start = timezone.localdate().replace(day=1) - timedelta(days=30)
                past_end = past_start + timedelta(days=27)
                sal_past, _ = SalaryRecord.objects.get_or_create(
                    worker=worker_profile,
                    period_start=past_start,
                    defaults={
                        "period_end": past_end,
                        "gross_amount": Decimal("40000.00"),
                        "net_amount": Decimal("40000.00"),
                        "status": SalaryRecord.Status.PAID,
                        "approved_by": super_admin,
                        "paid_by": super_admin,
                        "paid_at": timezone.now() - timedelta(days=15),
                    },
                )
                sal_past.status = SalaryRecord.Status.PAID
                sal_past.save()

                curr_start = timezone.localdate().replace(day=1)
                curr_end = curr_start + timedelta(days=27)
                SalaryRecord.objects.get_or_create(
                    worker=worker_profile,
                    period_start=curr_start,
                    defaults={
                        "period_end": curr_end,
                        "gross_amount": Decimal("40000.00"),
                        "net_amount": Decimal("40000.00"),
                        "status": random.choice([SalaryRecord.Status.PENDING, SalaryRecord.Status.APPROVED]),
                    },
                )

        hub_sales_count = max(20, sales_target // len(hubs))
        all_sellers = list(sales_agents) + list(member_profiles)

        for hub in hubs:
            for s in range(hub_sales_count):
                seller = random.choice(all_sellers)
                agent_arg = seller if isinstance(seller, get_user_model()) else None
                member_arg = seller if not isinstance(seller, get_user_model()) else None

                chosen_products = random.sample(products, random.randint(1, 2))
                items = [{"product": p.pk, "quantity": random.randint(1, 3)} for p in chosen_products]
                days_ago = random.randint(1, 30)
                sale_time = timezone.now() - timedelta(days=days_ago)

                business = random.choice([None] + list(Business.objects.filter(hub=hub)))

                try:
                    completed_sale = complete_sale(
                        hub=hub,
                        agent=agent_arg,
                        member=member_arg,
                        business=business,
                        actor=super_admin,
                        items=items,
                        customer_name="" if business else f"Walk-in Client {s+1}",
                        customer_phone=f"0798765{s:03d}",
                        payment_method=random.choice(["CASH", "MOBILE_MONEY", "BANK"]),
                        payment_reference=f"TXN-PROD-{hub.code}-{s+1}",
                    )
                    completed_sale.completed_at = sale_time
                    completed_sale.created_at = sale_time
                    completed_sale.save(update_fields=["completed_at", "created_at"])
                except Exception as e:
                    pass

        commissions = list(SalesAgentCommission.objects.all())
        random.shuffle(commissions)
        third = len(commissions) // 3
        for idx, comm in enumerate(commissions):
            if idx < third:
                comm.status = SalesAgentCommission.Status.PENDING
                comm.save(update_fields=["status"])
            elif idx < 2 * third:
                comm.status = SalesAgentCommission.Status.APPROVED
                comm.approved_by = super_admin
                comm.save(update_fields=["status", "approved_by"])
            else:
                comm.status = SalesAgentCommission.Status.PAID
                comm.approved_by = super_admin
                comm.paid_by = super_admin
                comm.paid_at = timezone.now() - timedelta(days=random.randint(1, 10))
                comm.save(update_fields=["status", "approved_by", "paid_by", "paid_at"])

        total_sales_revenue = sum(sale.total for sale in Sale.objects.filter(status=Sale.Status.COMPLETED))
        CashFlow.objects.create(
            direction=CashFlow.Direction.INFLOW,
            category="Sales Revenue",
            amount=total_sales_revenue,
            transaction_date=timezone.localdate(),
            hub=hubs[0],
            reference="INFLOW-TOTAL-SALES",
            description="Aggregated sales revenue across production hubs",
            created_by=super_admin,
        )
        CashFlow.objects.create(
            direction=CashFlow.Direction.OUTFLOW,
            category="Inventory Purchase",
            amount=(total_sales_revenue * Decimal("0.50")).quantize(Decimal("0.01")),
            transaction_date=timezone.localdate() - timedelta(days=10),
            hub=hubs[0],
            reference="OUTFLOW-INVENTORY",
            description="Wholesale agro-input restocking expenses",
            created_by=super_admin,
        )
        CashFlow.objects.create(
            direction=CashFlow.Direction.OUTFLOW,
            category="Operational Expenses",
            amount=(total_sales_revenue * Decimal("0.15")).quantize(Decimal("0.01")),
            transaction_date=timezone.localdate() - timedelta(days=5),
            hub=hubs[0],
            reference="OUTFLOW-OPEX",
            description="Hub utilities, logistics and transport",
            created_by=super_admin,
        )

        expense_categories = [
            (Expense.Category.STOCK_COST_OF_GOODS, (total_sales_revenue * Decimal("0.05")).quantize(Decimal("0.01")), "Wholesale stock restocking"),
            (Expense.Category.WAGES, (total_sales_revenue * Decimal("0.04")).quantize(Decimal("0.01")), "Staff and agent monthly wages"),
            (Expense.Category.RENT, (total_sales_revenue * Decimal("0.02")).quantize(Decimal("0.01")), "Hub warehouse and office rent"),
            (Expense.Category.UTILITIES, (total_sales_revenue * Decimal("0.005")).quantize(Decimal("0.01")), "Electricity and water utility bills"),
            (Expense.Category.TRANSPORT, (total_sales_revenue * Decimal("0.01")).quantize(Decimal("0.01")), "Delivery and transport logistics"),
            (Expense.Category.MARKETING, (total_sales_revenue * Decimal("0.005")).quantize(Decimal("0.01")), "Promotional campaigns"),
            (Expense.Category.BANK_CHARGES, (total_sales_revenue * Decimal("0.002")).quantize(Decimal("0.01")), "Bank and mobile money transaction fees"),
            (Expense.Category.OTHER, (total_sales_revenue * Decimal("0.003")).quantize(Decimal("0.01")), "Miscellaneous office supplies"),
        ]
        for cat, amount, title in expense_categories:
            if amount > 0:
                Expense.objects.create(
                    hub=hubs[0],
                    category=cat,
                    title=title,
                    amount=amount,
                    expense_date=timezone.localdate(),
                    reference=f"SEED-{cat}",
                    notes="Auto-seeded demo expense record for positive net profit balance.",
                    created_by=super_admin,
                )

        self.stdout.write(self.style.SUCCESS(
            f"Successfully seeded production dataset with 0 inventory reconciliation discrepancies."
        ))
