# Roles and permissions

Django permissions are assigned through the role matrix in `apps/accounts/roles.py`. Access is enforced at the view/API permission layer and, for hub-scoped records, by shared queryset scoping. A user must be authenticated, have the required model/action permission, and belong to or manage the record's hub when applicable.

## Roles

| Role | Intended scope |
| --- | --- |
| Super administrator | Full application administration and all hubs |
| Administrator | Organization-wide operational management |
| Hub manager | Assigned/managed hub operations, including local staff and transactions |
| Finance officer | Finance and operational reporting within assigned hubs |
| Sales agent | Own sales and commissions within the authorized hub |
| Worker | Own worker/payroll information |
| Beneficiary | Own profile, business, and related records |
| Viewer | Read-only records explicitly granted by the role matrix |

Role names are not a replacement for action permissions. In particular, approving or paying commissions and salaries, refunding sales, changing user roles, and editing hub membership require explicit permissions. Financial and inventory changes should use service-backed workflows rather than direct model edits.

Administrators can create and edit beneficiary profiles and businesses across the organization. Beneficiaries can create and edit only their own business records and profile; record-level scoping blocks access to another beneficiary's data.

Admins, Hub Managers, Sales Agents, and Super Admins can record sales. After changing the role matrix, refresh existing role groups so the corresponding buttons and routes use the updated grants:

```powershell
python manage.py setup_roles
```

## Administration guidance

Create named accounts, assign only the lowest role needed, and maintain hub membership independently from role assignment. Remove access promptly when staff leave. Protect administrator accounts with strong unique passwords and HTTPS; review audit events and periodic access lists. Do not grant super-administrator access for convenience.

Verify custom permissions after schema changes with:

```powershell
python manage.py migrate
python manage.py setup_roles
```

Run `python manage.py setup_roles` after changing the role permission matrix so existing role groups receive the updated grants.