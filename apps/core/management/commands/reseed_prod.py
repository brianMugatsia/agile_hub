import random
import re
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction

from apps.accounts.roles import Role
from apps.commissions.models import SalesAgentCommission
from apps.commissions.services import accrue_for_sale
from apps.finance.models import CashFlow, Expense, IncomeStatement, IncomeStatementItem
from apps.hubs.models import Hub, HubMembership
from apps.inventory.models import InventoryBalance, InventoryTransaction, Supplier, PurchaseOrder, PurchaseOrderLine
from apps.inventory.services import record_movement
from apps.members.models import Business, MemberProfile
from apps.payroll.models import SalaryRecord, WorkerProfile
from apps.products.models import Product
from apps.sales.models import Sale, SaleItem
from apps.sales.services import complete_sale
from apps.services.models import ServiceProvider, ServiceBooking, HubResource, ServiceType, ServiceCategory
from apps.commissions.models import ServiceCommission

User = get_user_model()

FIRST_NAMES = ["John", "Mary", "David", "Jane", "Peter", "Alice", "Joseph", "Grace", "Samuel", "Sarah", 
               "Daniel", "Esther", "Francis", "Catherine", "George", "Helen", "Isaac", "Irene", "James", "Joyce"]
LAST_NAMES = ["Kamau", "Otieno", "Mwangi", "Maina", "Njeri", "Anyango", "Wekesa", "Mutua", "Juma", "Okello",
              "Kipkorir", "Chepngetich", "Ochieng", "Njoroge", "Wanjiku", "Musa", "Hassan", "Ali", "Abdi", "Kariuki"]

class Command(BaseCommand):
    help = "Reseed the database with 3 months of realistic production-like data, preserving privileged accounts."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sales-per-hub",
            type=int,
            default=150,
            help="Target number of sales per hub over 3 months (default: 150).",
        )

    def get_random_name(self):
        return random.choice(FIRST_NAMES), random.choice(LAST_NAMES)

    @transaction.atomic
    def handle(self, *args, **options):
        if settings.DEBUG is False and not getattr(settings, "DEMO_DATA_ENABLED", False):
             raise CommandError("Seeding is disabled for this environment.")

        sales_per_hub = options["sales_per_hub"]
        
        self.stdout.write("Cleaning up existing data (preserving privileged accounts)...")

        # 1. Models to flush completely
        models_to_flush = [
            SaleItem, SalesAgentCommission, ServiceCommission, ServiceBooking, 
            ServiceProvider, HubResource, ServiceType, SalaryRecord, CashFlow,
            IncomeStatementItem, IncomeStatement, PurchaseOrderLine, PurchaseOrder,
            InventoryTransaction, Sale, Business, MemberProfile, WorkerProfile,
            InventoryBalance, Product, Supplier, Expense
        ]
        for model in models_to_flush:
            model.objects.all().delete()

        # 2. Users to delete (non-privileged)
        privileged_roles = [Role.SUPER_ADMIN, Role.ADMIN, Role.HUB_MANAGER, Role.FINANCE_OFFICER]
        deleted_count, _ = User.objects.exclude(role__in=privileged_roles).delete()
        self.stdout.write(f"Deleted {deleted_count} non-privileged users.")

        # 3. Seed Hubs if they don't exist
        hub_specs = [
            ("KIM-001", "Kimilili Hub", "Western", "Main Street, Kimilili", "0711100001"),
            ("MBA-002", "Mombasa Coastal Hub", "Coast", "Moi Avenue, Mombasa", "0711100002"),
            ("KSM-003", "Kisumu Lakeside Hub", "Western", "Oginga Odinga Road, Kisumu", "0711100003"),
        ]
        hubs = []
        for code, name, region, address, phone in hub_specs:
            hub, _ = Hub.objects.update_or_create(
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

        # 4. Ensure at least one privileged user per hub exists if not already there
        # (This keeps the system functional if it was totally empty except for superadmin)
        for i, hub in enumerate(hubs, start=1):
            # Manager
            User.objects.get_or_create(
                username=f"manager-{i}",
                defaults={
                    "email": f"manager{i}@agilehub.local",
                    "first_name": "Hub",
                    "last_name": f"Manager {i}",
                    "role": Role.HUB_MANAGER,
                    "hub": hub,
                    "is_active": True,
                }
            )
            # Finance
            User.objects.get_or_create(
                username=f"finance-{i}",
                defaults={
                    "email": f"finance{i}@agilehub.local",
                    "first_name": "Finance",
                    "last_name": f"Officer {i}",
                    "role": Role.FINANCE_OFFICER,
                    "hub": hub,
                    "is_active": True,
                }
            )

        # 5. Seed Products
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
            sku = f"SKU-{re.sub(r'[^A-Z]', '', name.upper())[:6]}-{random.randint(100,999)}"
            prod = Product.objects.create(
                sku=sku,
                name=name,
                category=category,
                cost_price=cost_price,
                selling_price=selling_price,
                reorder_level=reorder_level,
                is_active=True,
            )
            products.append(prod)
            for hub in hubs:
                InventoryBalance.objects.create(hub=hub, product=prod, quantity=1000)
                record_movement(
                    hub=hub, product=prod, quantity=1000,
                    kind=InventoryTransaction.Kind.RECEIPT,
                    notes="Initial stock seeding",
                    actor=User.objects.filter(role=Role.SUPER_ADMIN).first()
                )

        # 6. Seed Suppliers
        suppliers_data = [
            ("SUP-AGRO", "Agro-Inputs Wholesale Ltd", "0700112233", "Amina Supplier"),
            ("SUP-SEEDS", "East African Seed Co", "0700223344", "John Seed"),
            ("SUP-EQUIP", "Farm Equipment Distributors", "0700334455", "Peter Equip"),
        ]
        for code, name, phone, contact in suppliers_data:
            Supplier.objects.create(code=code, name=name, phone=phone, contact_name=contact, is_active=True)

        # 7. Seed Sales Agents and Members (3 months ago)
        start_date = timezone.now() - timedelta(days=90)
        sales_agents = []
        member_profiles = []
        
        for i in range(20):
            hub = hubs[i % len(hubs)]
            fname, lname = self.get_random_name()
            username = f"{fname.lower()}.{lname.lower()}.{i}"
            user = User.objects.create(
                username=username,
                email=f"{username}@example.com",
                first_name=fname,
                last_name=lname,
                role=Role.SALES_AGENT,
                hub=hub,
                is_active=True,
                phone_number=f"07{random.randint(10000000, 99999999)}"
            )
            user.set_password("password123")
            user.save()
            sales_agents.append(user)

        for i in range(30):
            hub = hubs[i % len(hubs)]
            fname, lname = self.get_random_name()
            username = f"member.{fname.lower()}.{i}"
            user = User.objects.create(
                username=username,
                email=f"{username}@example.com",
                first_name=fname,
                last_name=lname,
                role=Role.MEMBER,
                hub=hub,
                is_active=True,
                phone_number=f"07{random.randint(10000000, 99999999)}"
            )
            profile = MemberProfile.objects.create(
                user=user, hub=hub, phone_number=user.phone_number,
                location=f"{hub.region} Farm Zone {i}"
            )
            member_profiles.append(profile)
            if i < 15: # Half of members have businesses
                Business.objects.create(
                    member=profile, hub=hub, name=f"{lname} Agri-Enterprise",
                    business_type="Retail", status=Business.Status.ACTIVE
                )

        # 8. Seed Workers and 3 months of Salaries
        for i in range(10):
            hub = hubs[i % len(hubs)]
            fname, lname = self.get_random_name()
            username = f"worker.{fname.lower()}.{i}"
            user = User.objects.create(
                username=username,
                email=f"{username}@example.com",
                role=Role.WORKER,
                hub=hub,
                first_name=fname,
                last_name=lname,
                is_active=True
            )
            worker = WorkerProfile.objects.create(
                user=user, hub=hub, employee_code=f"W-{hub.code}-{i}",
                job_title="Operations Assistant", monthly_salary=Decimal("35000.00"),
                hired_on=start_date - timedelta(days=30)
            )
            
            # 3 Months of salary records
            for m in range(3):
                p_start = (start_date + timedelta(days=m*30)).replace(day=1)
                p_end = (p_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
                SalaryRecord.objects.create(
                    worker=worker, period_start=p_start, period_end=p_end,
                    gross_amount=worker.monthly_salary, net_amount=worker.monthly_salary,
                    status=SalaryRecord.Status.PAID,
                    paid_at=timezone.make_aware(timezone.datetime.combine(p_end, timezone.datetime.min.time())) + timedelta(days=2)
                )

        # 9. Seed Sales over 90 days
        self.stdout.write(f"Seeding {sales_per_hub * len(hubs)} sales over 90 days...")
        all_actors = sales_agents + member_profiles
        super_admin = User.objects.filter(role=Role.SUPER_ADMIN).first()

        for hub in hubs:
            for s in range(sales_per_hub):
                actor = random.choice(all_actors)
                agent = actor if isinstance(actor, User) else None
                member = actor if isinstance(actor, MemberProfile) else None
                
                days_ago = random.randint(0, 90)
                sale_time = timezone.now() - timedelta(days=days_ago)
                
                chosen_prods = random.sample(products, random.randint(1, 3))
                items = [{"product": p.pk, "quantity": random.randint(1, 5)} for p in chosen_prods]
                
                try:
                    sale = complete_sale(
                        hub=hub, agent=agent, member=member,
                        actor=super_admin, items=items,
                        payment_method=random.choice(["CASH", "MOBILE_MONEY"]),
                        customer_name=f"Customer {s}",
                    )
                    # Backdate
                    Sale.objects.filter(pk=sale.pk).update(created_at=sale_time, completed_at=sale_time)
                    # Commissions are handled by complete_sale -> accrue_for_sale
                except Exception as e:
                    self.stdout.write(f"Error seeding sale: {e}")

        # 10. Update Commissions status
        commissions = SalesAgentCommission.objects.all()
        for comm in commissions:
            if comm.created_at < timezone.now() - timedelta(days=20):
                comm.status = SalesAgentCommission.Status.PAID
                comm.paid_at = comm.created_at + timedelta(days=15)
                comm.save()
            elif comm.created_at < timezone.now() - timedelta(days=5):
                comm.status = SalesAgentCommission.Status.APPROVED
                comm.save()

        # 11. Seed Services
        service_types_data = [
            ("ST-SOIL", "Soil Testing & Analysis", "AGRONOMY", "FIXED", Decimal("2500.00")),
            ("ST-TRAC", "Tractor Hire (per Acre)", "HARVESTING", "PER_ACRE", Decimal("5000.00")),
            ("ST-DRY", "Grain Drying (per Bag)", "PROCESSING", "PER_KG", Decimal("200.00")),
            ("ST-AGRO", "Agronomy Consultation", "AGRONOMY", "FIXED", Decimal("1500.00")),
            ("ST-COLD", "Cold Storage (per Week)", "STORAGE", "PER_DAY", Decimal("1000.00")),
            ("ST-PACK", "Grading & Packaging", "PACKAGING", "PER_KG", Decimal("150.00")),
            ("ST-IRR", "Drip Irrigation Setup", "IRRIGATION", "FIXED", Decimal("8000.00")),
            ("ST-EXT", "Farmer Training & Extension", "EXTENSION", "PER_DAY", Decimal("1200.00")),
        ]
        service_types = []
        for code, name, cat, unit, rate in service_types_data:
            st = ServiceType.objects.create(
                code=code, name=name, category=cat, 
                pricing_unit=unit, standard_rate=rate, is_active=True
            )
            service_types.append(st)

        # Create multiple resources for hubs
        hub_resources = []
        for hub in hubs:
            for i, st in enumerate(service_types):
                hr = HubResource.objects.create(
                    hub=hub, service_type=st, 
                    name=f"{st.name} Unit {i+1}", 
                    total_count=random.randint(3, 8),
                    available_count=random.randint(2, 5),
                    in_use_count=random.randint(0, 3),
                    status=HubResource.Status.AVAILABLE,
                )
                hub_resources.append(hr)

        # Seed Service Providers
        providers = []
        for i in range(10):
            if i < 5 and i < len(member_profiles):
                member = member_profiles[i]
                sp = ServiceProvider.objects.create(
                    provider_type="INTERNAL",
                    member=member,
                    name=f"{member.user.get_full_name()} Services",
                    phone_number=member.phone_number,
                    service_category=random.choice(list(dict(ServiceCategory.choices).keys())),
                    status="ACTIVE"
                )
            else:
                fname, lname = self.get_random_name()
                sp = ServiceProvider.objects.create(
                    provider_type="EXTERNAL",
                    name=f"{lname} Agri-Services",
                    phone_number=f"07{random.randint(11000000, 19999999)}",
                    service_category=random.choice(list(dict(ServiceCategory.choices).keys())),
                    status="ACTIVE"
                )
            providers.append(sp)


        # Seed Service Bookings over 90 days
        self.stdout.write("Seeding service bookings...")
        for hub in hubs:
            resources = HubResource.objects.filter(hub=hub)
            for b in range(30): # 30 bookings per hub
                member = random.choice(member_profiles)
                resource = random.choice(resources)
                st = resource.service_type
                
                days_ago = random.randint(0, 90)
                start_time = timezone.now() - timedelta(days=days_ago)
                end_time = start_time + timedelta(hours=random.randint(2, 48))
                
                status = ServiceBooking.Status.COMPLETED if days_ago > 2 else random.choice(ServiceBooking.Status.values)
                
                booking = ServiceBooking.objects.create(
                    hub=hub, resource=resource, service_type=st,
                    member=member,
                    service_provider=random.choice(providers) if random.random() > 0.5 else None,
                    start_date=start_time,
                    end_date=end_time,
                    status=status,
                    quantity=Decimal(random.randint(1, 10)),
                    unit_rate=st.standard_rate,
                    created_by=super_admin,
                )
                # Manually set timestamps for history
                ServiceBooking.objects.filter(pk=booking.pk).update(created_at=start_time)

        # 12. Financials (Expenses and Cashflow)
        for hub in hubs:
            for d in range(0, 90, 7): # Weekly expenses
                date_exp = (start_date + timedelta(days=d)).date()
                Expense.objects.create(
                    hub=hub, category=Expense.Category.UTILITIES,
                    title="Weekly Utilities", amount=Decimal(random.randint(1000, 5000)),
                    expense_date=date_exp, created_by=super_admin
                )
                Expense.objects.create(
                    hub=hub, category=Expense.Category.TRANSPORT,
                    title="Logistics", amount=Decimal(random.randint(2000, 8000)),
                    expense_date=date_exp, created_by=super_admin
                )

        self.stdout.write(self.style.SUCCESS("Database reseeded successfully for 3 months of production."))
