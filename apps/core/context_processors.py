"""Builds the role-filtered sidebar.

Items whose URL name does not exist yet are skipped, so each stage's menu entries
appear automatically once that stage's URLs are added.
"""
from dataclasses import dataclass

from django.conf import settings
from django.urls import NoReverseMatch, reverse

from apps.accounts.roles import Role

SA, AD, HM, FO = Role.SUPER_ADMIN, Role.ADMIN, Role.HUB_MANAGER, Role.FINANCE_OFFICER
AG, WK, BN, VW = Role.SALES_AGENT, Role.WORKER, Role.BENEFICIARY, Role.VIEWER
EVERYONE = tuple(Role.values)


@dataclass(frozen=True)
class NavItem:
    label: str
    url_name: str
    icon: str
    roles: tuple
    section: str


NAV_ITEMS = (
    NavItem("Dashboard", "core:dashboard", "grid", EVERYONE, "Overview"),
    NavItem("Notifications", "notifications:list", "inbox", EVERYONE, "Overview"),
    NavItem("Hubs", "hubs:list", "map-pin", (SA, AD, HM, VW), "Operations"),
    NavItem("Beneficiaries", "beneficiaries:list", "heart", (SA, AD, HM, BN), "Operations"),
    NavItem("Products", "products:list", "package", (SA, AD, HM, FO, AG, VW), "Operations"),
    NavItem("Inventory", "inventory:list", "layers", (SA, AD, HM, FO), "Operations"),
    NavItem("Sales", "sales:list", "shopping-cart", (SA, AD, HM, FO, AG, VW), "Operations"),
    NavItem("Sales Agents", "sales:agent_list", "user-check", (SA, AD, HM), "Operations"),
    NavItem("Commissions", "commissions:list", "percent", (SA, AD, HM, FO, AG), "Staff & Payments"),
    NavItem("Workers", "payroll:worker_list", "briefcase", (SA, AD, HM, FO), "Staff & Payments"),
    NavItem("Workers' Salaries", "payroll:salary_list", "credit-card", (SA, AD, HM, FO, WK), "Staff & Payments"),
    NavItem("Finance", "finance:income_statement", "trending-up", (SA, AD, HM, FO, BN, VW), "Finance & Insight"),
    NavItem("Reports", "reports:index", "bar-chart", (SA, AD, HM, FO, VW), "Finance & Insight"),
    NavItem("Users", "accounts:user_list", "users", (SA, AD), "Administration"),
    NavItem("Audit Logs", "audit:list", "shield", (SA,), "Administration"),
    NavItem("Settings", "core:settings", "settings", (SA, AD), "Administration"),
)


def navigation(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}

    entries = []
    for item in NAV_ITEMS:
        if user.role not in item.roles:
            continue
        try:
            url = reverse(item.url_name)
        except NoReverseMatch:
            continue
        entries.append({"label": item.label, "url": url, "icon": item.icon, "section": item.section})

    # The longest matching URL prefix wins, so /payroll/ and /payroll/salaries/ never both light up.
    active = None
    for entry in entries:
        if request.path.startswith(entry["url"]) and (
            active is None or len(entry["url"]) > len(active["url"])
        ):
            active = entry

    sections = []
    for entry in entries:
        entry["active"] = entry is active
        if not sections or sections[-1]["title"] != entry["section"]:
            sections.append({"title": entry["section"], "items": []})
        sections[-1]["items"].append(entry)

    return {
        "nav_sections": sections,
        "CURRENCY_CODE": settings.CURRENCY_CODE,
        "DEMO_MODE": getattr(settings, "DEMO_MODE", False),
        "DEVELOPMENT_MODE": getattr(settings, "DEVELOPMENT_MODE", False),
    }