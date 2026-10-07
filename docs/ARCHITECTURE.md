# Architecture

Agile Hub is a Django monolith organized as business-domain apps. `config` owns settings and URL composition; `apps/core` provides shared views, scoping, navigation, and templates; domain apps own their models, web routes, API routes, and transactional services.

## Domains

- Accounts and roles: authentication, role assignments, and permission synchronization.
- Hubs: hub locations and user membership.
- Products and inventory: product catalog, per-hub balances, and immutable stock movements.
- Sales: sale headers/items and sale lifecycle.
- Commissions and payroll: accrual/approval/payment state machines.
- Beneficiaries: beneficiary profiles and associated businesses.
- Finance and reports: cash-flow records and operational summaries.
- Audit and notifications: traceable events and user-facing updates.

## Write path

Stateful workflows are implemented in domain service functions and use `transaction.atomic`; they validate permissions and current state, lock relevant rows, write the business records, and append audit/notification records. Inventory balances are maintained per hub; `Product.stock_on_hand` is an aggregate maintained by the stock service. Callers should not update these records directly.

Run migrations before deploying code that relies on new fields, and run `setup_roles` after migrating to synchronize the application role permission matrix.

## Data and reporting boundary

Money is represented with fixed-scale decimal fields, with KES as the default currency. Cash flow records represent recorded inflows/outflows, and report calculations summarize these operational data. The current schema is not a double-entry ledger: it does not provide a full chart of accounts, journal entries, balancing controls, or audit-reviewed statements. Financial outputs should be labeled operational and reconciled independently before accounting/tax use.