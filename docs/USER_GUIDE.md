# Agile Hub user guide

This guide follows the normal application screens. The sidebar is role-filtered, so you only see sections available to your account. If an expected screen or button is missing, ask an administrator to check your role, permissions, and hub membership; do not share accounts.

## 1. Sign in and orient yourself

1. Open the application URL and sign in with your username or email and password.
2. Start at **Dashboard**. Use the sidebar to move between **Operations**, **Staff & Payments**, **Finance & Insight**, and **Administration**.
3. Open your profile to update your contact details or change your password. Use **Notifications** to read alerts such as low-stock warnings, commission accruals, and payroll status changes.
4. Sign out when finished, especially on a shared device.

Lists generally provide search, filters, pagination, and CSV/Excel downloads where enabled. Use **Details** to inspect a record. Use **Edit** only when it is offered; not every record can be edited, especially records that represent financial or inventory history.

## 2. Accounts, roles, hubs, and beneficiaries

### Create a user and grant access

An Admin or Super Admin opens **Users → Add user**, enters the user's name, email, username, phone, role, and initial password, then saves. Admins can assign operational roles, but only Super Admins can grant Admin or Super Admin. Assign the least-privileged role that suits the person's job.

For hub-scoped staff, open **Hubs** and add the person as a member of the correct hub; hub membership is separate from the person's role. A Hub Manager can work only in hubs they manage or are actively assigned to. Keep accounts active only while access is needed; inactive users cannot sign in.

### Set up hubs

Create a hub before assigning its staff, products, or transactions. A Super Admin creates hubs. An Admin or an authorized Hub Manager can edit a hub they are allowed to manage. Check the hub's status and manager/membership before entering operations; inactive hubs cannot accept sales or stock movements.

### Add beneficiaries and businesses

1. An administrator creates a user with the **Beneficiary** role.
2. Under **Beneficiaries**, choose **Add beneficiary**, select that user, and complete the profile and hub assignment.
3. Under **Businesses**, choose **Add business**, select the beneficiary, and enter the business name, contact/registration details, hub, and status.
4. To update either record, choose its **Edit** action. A beneficiary can update only their own profile/businesses; administrators can manage them across the organization.

Set a business to active before associating it with a sale. Business/hub associations must agree.

## 3. Products, stock, suppliers, and purchase orders

### Prepare the catalogue and opening stock

1. Add products under **Products** with a unique SKU, name, selling price, cost price, unit, and reorder level.
2. Record the opening stock using **Inventory → Record movement**. Choose the correct hub, product, movement type/direction, quantity, and reference or note. A positive whole-number quantity is required.
3. Use the **Inventory** list to review the stock ledger and hub balances. Products can be imported from the supplied spreadsheet template; preview the import and fix/download rejected rows before confirming it.

Inventory transactions are the stock history. Do not try to correct an old transaction by editing or deleting it; record the appropriate supported movement so the ledger retains its history.

### Reorder stock

1. Add an active supplier under **Purchase orders → Suppliers**.
2. When items reach their reorder levels, create a reorder purchase order for the correct hub and supplier. The system includes active low-stock products and proposes quantities.
3. When deliveries arrive, open the order's **Receive** action and enter the quantity received for each line. Partial receipts are supported; receive the balance later. Receiving writes inventory movements and updates the order status.

## 4. Record and reconcile sales

1. Admins, Hub Managers, Sales Agents, and Super Admins can record sales. Under **Sales**, choose **New sale**. Select an active hub, an active product, and a positive quantity. Add customer details, an optional active business, payment method/reference, and notes as appropriate. Finance Officers, Viewers, Workers, and Beneficiaries do not have sale-entry permission.
2. Submit the sale. The application checks available stock, records the completed sale and stock-out movement, and accrues an agent commission when the seller is a Sales Agent. Cash/mobile/bank sales record an income cash-flow entry; credit sales do not record cash received.
3. Use the Sales list and detail page to review it. The **Edit** action changes only customer name/phone, payment reference, and notes. Product lines, quantity, amount, payment method, hub, and business are locked because they affect stock, cash flow, and commissions.
4. Refund a completed sale only through the authorized refund workflow with a reason (the default role matrix grants this action to Super Admin). It records returned stock and, for non-credit sales, a refund cash-flow outflow. Do not use a regular stock adjustment to disguise a sales refund.
5. Open **Sales / stock reconciliation**, choose the date range, and review matched movements and discrepancies. It compares sale quantities with the linked inventory ledger within hubs you can access. Investigate each unmatched or quantity-mismatched entry against the source sale and movement history; correct the underlying process with an authorized transaction, not by editing ledger records.

Sales and inventory exports are available where the list offers them. Check the hub/date filters before exporting so the file contains the intended scope.

## 5. Staff, commissions, and payroll

### Staff and payroll

1. Create a user with the **Worker** role under **Users**.
2. Under **Workers**, choose **Add worker** and assign that user to the right hub. Enter employee ID, position, monthly salary, hire date, and active status.
3. A user with salary-entry permission opens **Workers' Salaries → Prepare salary**, selects the worker and period, enters gross pay and deductions, and submits. Net pay is gross pay less deductions. New records enter **Pending approval**.
4. An authorized approver reviews the period and amount, then chooses **Approve**. A Finance Officer can then choose **Pay** for an approved record. Payment marks it paid, creates a Payroll cash-flow outflow, records an audit event, and notifies the worker.

Admins can prepare and approve salaries but do not have the normal Pay action; Finance Officers can prepare, approve, and pay. Hub Managers can create worker profiles but cannot approve/pay salary records. Worker profiles currently have a list/create screen but no normal-screen edit action. Workers can view only their own payroll. There is no normal-screen salary rejection action at present; correct a pending record through the available workflow or seek administrator assistance rather than assuming the unused Rejected status is actionable.

### Agent commissions

Commissions are accrued automatically for eligible completed Sales Agent sales. The default rate is 20% unless an effective-dated setting applies. A Super Admin opens **Commissions → Settings** and enters a user-facing percentage, such as `12.5` for 12.5%, plus the effective date. The new rate applies to sales completed from that date; existing commission records retain their stored rate.

An authorized approver reviews pending commissions and approves or rejects them; rejection requires a reason. A Finance Officer pays approved commissions. Payment creates a Sales commission cash-flow outflow and sends the agent a notification. Reversal requires a reason. Agents can view their own statement; staff with broader commission permissions can review the list and sale details.

## 6. Finance and reports

### Finance screens

- **Income statement** defaults to the current month. Enter a start date, end date, or both to select a period (maximum 366 days). It summarizes completed-sale revenue, cost of goods, accrued commissions, payroll, and any existing statement expense items. Those statement items do not currently have a normal-screen entry form.
- **Cash flow** contains both manually recorded transactions and transactions generated by sales, refunds, commission payments, and salary payments. Authorized users can choose **Record cash flow** for a supported manual entry. Associate a business only with its hub; the form rejects a conflicting hub/business selection.
- **Break-even**, **Projections**, and **Ratios** are decision-support calculations. Break-even and projections use values submitted on the screen and do not save a forecast.
- **Assets**, **Liabilities**, **Equity**, **Startup costs**, and **Funding sources** are currently browse/report screens, not complete data-entry workflows in the normal application. Do not treat them as maintained ledgers.

Finance Officers and Hub Managers see hub-scoped records. Beneficiaries see their own permitted business data. Financial totals depend on the stored operational records and date/status rules, so reconcile them against source transactions before using them for decisions.

### Reports, exports, approvals, and audit history

Use **Reports** for available operational summaries and **Sales / stock reconciliation** for sales-to-ledger checks. Use **Approval inbox** for pending salary and commission approvals where available; commission rejection is handled from the commission workflow. Export only the records you are authorized to access.

**Audit Logs** are restricted to Super Admins and record important actions such as sales, stock movements, payments, approvals, refunds, and administration changes. Review them when checking who performed a recorded operation.

## 7. Role quick reference

| Role | Typical work |
| --- | --- |
| Super Admin | Full system administration, hubs, users, permissions, and commission settings |
| Admin | Organization users and operations; beneficiary/business maintenance; prepare/approve salaries |
| Hub Manager | Assigned hub operations, stock, purchase orders, sales, and local worker profiles |
| Finance Officer | Hub-scoped finance, commission/payroll review and payment, exports |
| Sales Agent | Record sales and view own commission history |
| Worker | View own salary records and notifications |
| Beneficiary | View/update own profile and businesses and permitted related data |
| Viewer | Read-only operational and reporting access in assigned hubs |

Actual actions are controlled by permissions as well as role and hub scope. When access differs from this summary, the current permission matrix and the buttons shown for your account take precedence.

## 8. Practice safely with demo records

For a local development environment, follow the [README setup instructions](../README.md#demo-data) and seed sample data using `seed_demo_data`. Use a separate demo database for disposable experiments, not production. Never seed real customer or payroll data into a shared demo instance.

## Important financial limitation

Agile Hub is an operational management system, not a general ledger, double-entry accounting package, or audited HR/payroll system. Cash-flow entries are not editable through the normal UI after creation, and the asset/liability/equity/startup/funding screens do not have normal-screen entry forms. Commission reversals change the commission status, but a paid commission is not automatically represented by a recovery/refund cash-flow transaction. Confirm financial statements and any paid-commission reversal with an accountant and the relevant approver before relying on totals for statutory reporting.
