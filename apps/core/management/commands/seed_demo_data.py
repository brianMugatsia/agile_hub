import calendar
import random
import re
import time
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.accounts.roles import Role
from apps.members.models import Business, MemberProfile
from apps.commissions.models import SalesAgentCommission
from apps.commissions.services import accrue_for_sale
from apps.hubs.models import Hub, HubMembership
from apps.inventory.models import InventoryBalance, InventoryTransaction, Supplier, PurchaseOrder, PurchaseOrderLine
from apps.inventory.services import record_movement, create_reorder_order
from apps.payroll.models import SalaryRecord, WorkerProfile
from apps.products.models import Product
from apps.sales.models import Sale, SaleItem
from apps.sales.services import complete_sale


class Command(BaseCommand):
    help = "Create rich sample records with 10 sales agents (5 as members), purchase orders, sales, commissions, payroll, and approval/paid workflows across hubs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sales",
            type=int,
            default=150,
            help="Target number of demo sales across hubs (default: 150).",
        )
        parser.add_argument(
            "--batch",
            default="sample",
            help="Short alphanumeric batch label.",
        )

    def handle(self, *args, **options):
        settings_module = getattr(settings, "SETTINGS_MODULE", "")
        if settings_module == "config.settings.production":
            raise CommandError("Sample seeding is disabled under production settings.")
        if not getattr(settings, "DEMO_DATA_ENABLED", False):
            raise CommandError("Sample seeding is disabled for this database.")

        Hub.objects.filter(code="NAI-001").update(
            code="KIM-001",
            name="Kimilili Hub",
            region="Western",
            address="Main Street, Kimilili"
        )

        sales_target = options["sales"]
        batch = options["batch"]
        if not 0 <= sales_target <= 10_000:
            raise CommandError("--sales must be between 0 and 10000.")

        User = get_user_model()

        # Define 3 realistic hubs
        hub_specs = [
            ("KIM-001", "Kimilili Hub", "Western", "Main Street, Kimilili"),
            ("MBA-002", "Mombasa Coastal Hub", "Coast", "Moi Avenue, Mombasa"),
            ("KSM-003", "Kisumu Lakeside Hub", "Western", "Oginga Odinga Road, Kisumu"),
        ]

        hubs = []
        for code, name, region, address in hub_specs:
            hub, _ = Hub.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "region": region,
                    "address": address,
                    "status": Hub.Status.ACTIVE,
                },
            )
            hubs.append(hub)

        # Create Super Admin if not exists
        super_admin, _ = User.objects.update_or_create(
            username="agile",
            defaults={
                "email": "agile@gmail.com",
                "first_name": "Super",
                "last_name": "Admin",
                "role": Role.SUPER_ADMIN,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        super_admin.set_password("agile")
        super_admin.save()

        # Create Hub Managers and Finance Officers
        role_configs = [
            ("manager", Role.HUB_MANAGER, "Hub Manager"),
            ("finance", Role.FINANCE_OFFICER, "Finance Officer"),
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
                        "last_name": f"User {i}",
                        "role": role,
                        "hub": hub,
                        "is_active": True,
                    },
                )
                user.set_password("password123")
                user.save()
                if role == Role.HUB_MANAGER:
                    HubMembership.objects.get_or_create(
                        hub=hub, user=user, defaults={"title": title}
                    )

        # Create exactly 10 Sales Agents (5 of whom are also members)
        sales_agents = []
        for i in range(1, 11):
            hub = hubs[(i - 1) % len(hubs)]
            username = f"salesagent-{i}"
            email = f"salesagent{i}@agilehub.local"
            agent_user, _ = User.objects.update_or_create(
                username=username,
                defaults={
                    "email": email,
                    "first_name": f"Sales Agent",
                    "last_name": f"Number {i}",
                    "role": Role.SALES_AGENT,
                    "hub": hub,
                    "is_active": True,
                },
            )
            agent_user.set_password("password123")
            agent_user.save()
            HubMembership.objects.get_or_create(
                hub=hub, user=agent_user, defaults={"title": "Sales Agent"}
            )
            sales_agents.append(agent_user)

            # First 5 sales agents are also members
            if i <= 5:
                profile, _ = MemberProfile.objects.get_or_create(
                    user=agent_user,
                    defaults={
                        "phone_number": f"07112233{i:02d}",
                        "address": f"{hub.name} Region",
                        "hub": hub,
                        "notes": f"Sales agent and member #{i}",
                    },
                )
                Business.objects.update_or_create(
                    member=profile,
                    name=f"Agent Member Business {i}",
                    defaults={
                        "hub": hub,
                        "business_type": "Retail & Distribution",
                        "amount": Decimal("15000.00"),
                        "is_paid": True,
                        "status": Business.Status.ACTIVE,
                    },
                )

        # Create Products & Inventory per hub
        products_data = [
            ("Certified Maize Seeds (10kg)", "Seeds", Decimal("1500.00"), Decimal("2000.00"), 20),
            ("NPK Fertilizer (50kg)", "Inputs", Decimal("3500.00"), Decimal("4500.00"), 10),
            ("DAP Fertilizer (50kg)", "Inputs", Decimal("4000.00"), Decimal("5200.00"), 10),
            ("Knapsack Sprayer", "Equipment", Decimal("2500.00"), Decimal("3500.00"), 5),
            ("Pesticide Spray (1L)", "Protection", Decimal("800.00"), Decimal("1200.00"), 15),
            ("Hybrid Tomato Seeds (50g)", "Seeds", Decimal("1200.00"), Decimal("1800.00"), 10),
            ("Urea Fertilizer (50kg)", "Inputs", Decimal("3800.00"), Decimal("4800.00"), 10),
        ]

        products = []
        for name, category, cost_price, selling_price, reorder_level in products_data:
            prod, _ = Product.objects.get_or_create(
                sku=f"SKU-{name[:3].upper()}-01",
                defaults={
                    "name": name,
                    "category": category,
                    "cost_price": cost_price,
                    "selling_price": selling_price,
                    "reorder_level": reorder_level,
                },
            )
            products.append(prod)
            for hub in hubs:
                balance, _ = InventoryBalance.objects.get_or_create(
                    hub=hub, product=prod, defaults={"quantity": 250}
                )
                balance.quantity = 250
                balance.save()

                record_movement(
                    hub=hub,
                    product=prod,
                    quantity=50,
                    kind=InventoryTransaction.Kind.RECEIPT,
                    notes="Initial demo stock batch",
                    actor=super_admin,
                )

        # Create Suppliers and Purchase Order data
        suppliers_data = [
            ("SUP-AGRO", "Agro-Inputs Wholesale Ltd"),
            ("SUP-SEEDS", "East African Seed Co"),
            ("SUP-EQUIP", "Farm Equipment Distributors"),
        ]
        suppliers = []
        for code, name in suppliers_data:
            supplier, _ = Supplier.objects.get_or_create(
                code=code,
                defaults={"name": name, "is_active": True, "contact_name": "Sales Manager", "phone": "0700112233"}
            )
            suppliers.append(supplier)

        for hub in hubs:
            supplier = random.choice(suppliers)
            try:
                create_reorder_order(hub=hub, supplier=supplier, actor=super_admin, notes="Seeded purchase reorder")
            except Exception:
                pass

        # Create Members, Businesses, Workers, Salary Records, and Sales per hub
        for hub in hubs:
            hub_local_agents = [agent for agent in sales_agents if agent.hub_id == hub.pk] or sales_agents

            # Force low stock items for dashboard alerts
            low_stock_items = random.sample(products, 2)
            for lprod in low_stock_items:
                bal = InventoryBalance.objects.get(hub=hub, product=lprod)
                bal.quantity = max(1, lprod.reorder_level - 2)
                bal.save()

            # Regular Members & Businesses (5 per hub)
            for m in range(1, 6):
                m_user, _ = User.objects.update_or_create(
                    username=f"member-{hub.code.lower()}-{m}",
                    defaults={
                        "email": f"member{m}@{hub.code.lower()}.local",
                        "first_name": f"Member {m}",
                        "last_name": hub.region,
                        "role": Role.MEMBER,
                        "hub": hub,
                    },
                )
                m_user.set_password("password123")
                m_user.save()

                profile, _ = MemberProfile.objects.get_or_create(
                    user=m_user,
                    defaults={
                        "phone_number": f"0712345{m}0",
                        "address": f"{hub.region} County",
                        "hub": hub,
                        "notes": f"Comprehensive member in {hub.name}",
                    },
                )
                contrib_amount = Decimal("10000.00") if (m % 2 == 0) else Decimal("0.00")
                Business.objects.update_or_create(
                    member=profile,
                    name="Land Buying Contribution",
                    defaults={
                        "hub": hub,
                        "business_type": "Land Buying",
                        "amount": contrib_amount,
                        "is_paid": (contrib_amount > 0),
                        "status": Business.Status.ACTIVE,
                    },
                )

            # Workers & Salary Records (3 per hub)
            for w in range(1, 4):
                w_user, _ = User.objects.update_or_create(
                    username=f"worker-{hub.code.lower()}-{w}",
                    defaults={
                        "email": f"worker{w}@{hub.code.lower()}.local",
                        "first_name": f"Worker {w}",
                        "last_name": hub.region,
                        "role": Role.WORKER,
                        "hub": hub,
                    },
                )
                w_user.set_password("password123")
                w_user.save()

                worker_profile, _ = WorkerProfile.objects.get_or_create(
                    user=w_user,
                    hub=hub,
                    defaults={
                        "employee_code": f"EMP-{hub.code}-{w:02d}",
                        "job_title": "Operations Assistant",
                        "monthly_salary": Decimal("35000.00"),
                        "hired_on": timezone.localdate() - timedelta(days=90),
                        "is_active": True,
                    },
                )
                SalaryRecord.objects.get_or_create(
                    worker=worker_profile,
                    period_start=timezone.localdate().replace(day=1),
                    defaults={
                        "period_end": timezone.localdate().replace(day=28),
                        "gross_amount": worker_profile.monthly_salary,
                        "net_amount": worker_profile.monthly_salary,
                        "status": SalaryRecord.Status.PENDING,
                    },
                )

            # Sales & Commissions across sales agents
            hub_sales_count = max(15, sales_target // len(hubs))
            for s in range(hub_sales_count):
                chosen_agent = random.choice(hub_local_agents)
                chosen_products = random.sample(products, 2)
                items = [{"product": p.pk, "quantity": random.randint(1, 4)} for p in chosen_products]
                try:
                    completed_sale = complete_sale(
                        hub=hub,
                        agent=chosen_agent,
                        actor=super_admin,
                        items=items,
                        customer_name=f"Customer {s+1} ({hub.region})",
                        customer_phone=f"0798765{s:03d}",
                        payment_reference=f"DEMO-SALE-{hub.code}-{s+1}",
                    )
                    commission = SalesAgentCommission.objects.filter(sale=completed_sale).first()
                    if commission:
                        commission.status = SalesAgentCommission.Status.PENDING
                        commission.save()
                except Exception as e:
                    pass

        # For the entire system: after approval, make as paid (commissions, salary records, and businesses)
        for commission in SalesAgentCommission.objects.all():
            commission.status = SalesAgentCommission.Status.APPROVED
            commission.approved_by = super_admin
            commission.save(update_fields=["status", "approved_by"])
            commission.status = SalesAgentCommission.Status.PAID
            commission.paid_by = super_admin
            commission.paid_at = timezone.now()
            commission.save(update_fields=["status", "paid_by", "paid_at"])

        for salary in SalaryRecord.objects.all():
            salary.status = SalaryRecord.Status.APPROVED
            salary.approved_by = super_admin
            salary.save(update_fields=["status", "approved_by"])
            salary.status = SalaryRecord.Status.PAID
            salary.paid_by = super_admin
            salary.paid_at = timezone.now()
            salary.save(update_fields=["status", "paid_by", "paid_at"])

        Business.objects.all().update(is_paid=True)

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded 10 sales agents (5 as members), purchase orders, sales, commissions, payroll, and set all approved items as paid across the system."))
