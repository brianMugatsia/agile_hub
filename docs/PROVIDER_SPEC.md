\# TASK: Update the Existing Agile Hub Application



Act as a senior full-stack software engineer. Inspect and extend my existing Agile Hub application to implement financial management, service costing, profit calculation, commission management, and service provider management.



IMPORTANT: This is an existing application. Do not create a new project or rewrite the entire application. Inspect the current codebase, understand its architecture, and modify the existing code while preserving all working functionality.



\## 1. Inspect the Existing Application First



Before making changes:



1\. Inspect the project structure and identify the frontend, backend, database, authentication, and authorization systems.

2\. Examine existing member management, services, sales, expenses, inventory, financial records, and commission functionality.

3\. Identify existing models, database relationships, API endpoints, frontend components, and financial calculations.

4\. Reuse existing functionality wherever possible.

5\. Identify the safest way to integrate the new features without duplicating existing models or business logic.



Prepare a brief implementation plan and then implement the changes incrementally.



Do not delete existing data, replace the database, or introduce breaking changes unnecessarily.



\## 2. Service Provider Classification



Agile Hub has two distinct categories of service providers.



\### A. Internal Service Providers



Internal service providers are registered members of Agile Hub.



Requirements:



\* Every internal service provider must be associated with an existing Agile Hub member record.

\* Reuse the existing member database and member identification system.

\* Do not create duplicate member accounts.

\* Allow authorized administrators to register eligible members as internal service providers.

\* Allow internal service providers to provide services offered through Agile Hub.

\* Track the services they provide, transactions completed, revenue generated, commissions earned, commissions paid, and outstanding balances.

\* Maintain the relationship between the service provider profile and the underlying member account.

\* Ensure that changing a service provider's status does not automatically deactivate the member's entire account.



\### B. External Service Providers



External service providers are NOT members of Agile Hub.



They are independent individuals, businesses, or organizations that provide services offered through Agile Hub.



Requirements:



\* External service providers must not be required to register as Agile Hub members.

\* They must not be assigned fake member IDs or automatically created as members.

\* Manage them through a separate external service provider profile or an appropriately designed shared service provider model.

\* Store their name or business name, contact information, service category, and other relevant details.

\* Allow administrators to register, update, activate, suspend, and deactivate external service providers.

\* Allow external service providers to be assigned to services offered through Agile Hub.

\* Track their completed transactions, revenue generated, commissions earned, commissions paid, and outstanding balances.

\* Support payment and commission records without requiring a member account.

\* Do not automatically grant them access to the internal member portal.

\* If external providers later need application access, implement it through a separate, explicitly authorized access mechanism.



\### Important database design rule



Internal and external providers perform the same general business function: they provide services offered by Agile Hub.



Design the system to share common service provider functionality without incorrectly treating both categories as members.



Inspect the existing architecture before choosing the implementation.



A suitable design may use a common service provider entity with a provider type and an optional relationship to a member:



\* `provider\_type`: INTERNAL or EXTERNAL.

\* `member`: Optional relationship to an existing member.

\* Internal providers must reference a valid existing member.

\* External providers must not require a member relationship.



Enforce these rules through backend validation and, where appropriate, database constraints.



Alternatively, extend the existing models if that is more compatible with the application's architecture.



Do not create unnecessary duplicate models or break existing relationships.



\## 3. Service Provider Lifecycle and Status



Support the following service provider statuses:



\* Active.

\* Dormant.

\* Suspended.

\* Inactive.



An active provider is eligible to provide services according to the hub's rules.



A dormant provider has not completed a qualifying service transaction within a configurable period.



Use 90 days as the default dormancy period unless the application already defines another rule.



The administrator must be able to adjust this period.



Dormancy must be based on service activity rather than the date of the last commission payment.



A suspended provider is temporarily prohibited from providing new services.



An inactive provider is no longer participating in the hub's service operations.



Implement:



\* Automatic identification of dormant providers.

\* Filtering by provider type and status.

\* Provider reactivation.

\* Suspension with a recorded reason.

\* Preservation of historical service transactions and financial records.



Changing a provider's status must not delete their financial history.



For internal providers, changing the provider status must not automatically change the underlying member's membership status.



For external providers, changing their provider status must not affect unrelated member accounts.



\## 4. Financial Management



Implement or extend the existing financial management functionality to track:



\* Gross incoming revenue.

\* Returns and refunds.

\* Discounts, where applicable.

\* Net revenue.

\* Direct service costs.

\* Transportation expenses.

\* Sales expenses.

\* Administrative expenses.

\* Other operational expenses.

\* Gross profit.

\* Profit before commission.

\* Service provider commission.

\* Net profit retained by Agile Hub.



Reuse existing transaction and expense records where possible.



Use decimal-safe financial calculations rather than floating-point arithmetic.



\### Default financial formulas



Net Revenue = Gross Revenue - Returns - Discounts



Gross Profit = Net Revenue - Direct Service Costs



Sales Expense = Applicable Sales Expense Base × Sales Expense Rate



Profit Before Commission = Gross Profit - Applicable Operating Expenses



Service Provider Commission = Applicable Commission Base × Commission Rate



Net Hub Profit = Profit Before Commission - Service Provider Commission



Ensure that expenses are not deducted twice and that the same commission is not recorded more than once.



The administrator must be able to configure the commission calculation base, such as gross profit or profit after applicable expenses.



The system must display the selected calculation basis clearly.



\## 5. Service Provider Commission



The default service provider commission rate is 20%.



Both internal and external service providers can earn commissions for eligible services they provide through Agile Hub.



The commission rules must not depend on whether the provider is an Agile Hub member.



However, the administrator must be able to configure different rates for internal and external providers.



Support:



\* A default commission rate.

\* An internal provider commission rate.

\* An external provider commission rate.

\* Optional service-specific rates, if supported by the existing architecture.

\* Configurable commission calculation bases.



\### Example



Suppose a service generates:



Revenue: KSh 10,000



Direct service costs: KSh 5,000



Operating expenses: KSh 500



Profit before commission: KSh 4,500



Commission rate: 20%



Service provider commission: KSh 900



Net hub profit: KSh 3,600



This example assumes the commission is calculated from profit after operating expenses.



Use the administrator's actual configuration when calculating commissions.



\### Commission records



Each commission record should contain, where applicable:



\* Service provider.

\* Provider type.

\* Originating transaction.

\* Service provided.

\* Commission rate applied.

\* Commission calculation basis.

\* Eligible amount.

\* Commission amount.

\* Status.

\* Creation date.

\* Payment date, if paid.



Support the appropriate statuses, such as pending, approved, paid, and reversed.



Prevent duplicate commission records and duplicate payments.



A commission must not be marked as paid without a valid payment record.



When a service transaction is refunded or cancelled, apply the appropriate commission reversal or adjustment while preserving the original financial history.



\## 6. Sales Expenses



Introduce a default sales expense rate of 5%.



The administrator must be able to configure:



\* The sales expense rate.

\* The calculation base.

\* Whether the rule applies globally, by service, or by category.



Possible calculation bases include gross revenue, net revenue, or gross profit.



For example, if the configured rate is 5% of net revenue and net revenue is KSh 10,000:



Sales Expense = KSh 10,000 × 5% = KSh 500.



Avoid recording duplicate sales expenses if the existing sales module already records them.



\## 7. Transportation and Other Expenses



Support these expense categories:



\* Transportation.

\* Sales.

\* Administration.

\* Direct service costs.

\* Other operating expenses.



Transportation must support two scenarios.



\*\*Scenario A: Hub transportation expense\*\*



Agile Hub incurs a transportation cost while providing a service. Record it as an applicable operating expense.



\*\*Scenario B: Transportation provided by a service provider\*\*



An internal or external provider supplies transportation as a service offered through Agile Hub.



In this scenario:



\* Create or associate the appropriate service transaction.

\* Associate it with the correct provider.

\* Calculate revenue and applicable costs.

\* Calculate the provider's commission using the configured rules.

\* Track the amount payable to the provider.

\* Avoid incorrectly treating the same payment as both a transportation expense and a separate duplicate commission.



An internal transporter must be linked to an existing Agile Hub member.



An external transporter must not require membership.



\## 8. Administrator Financial Settings



Extend the existing administrative settings interface.



Allow authorized administrators to configure:



\* Default commission rate: 20%.

\* Internal service provider commission rate.

\* External service provider commission rate.

\* Default sales expense rate: 5%.

\* Sales expense calculation basis.

\* Commission calculation basis.

\* Transportation expense rules.

\* Administrative expense rules.

\* Other applicable rates.

\* Provider dormancy period.



The administrator must be able to update these settings without modifying application source code.



Validate rates and reject invalid negative values.



Record every significant rate change, including:



\* Previous value.

\* New value.

\* Administrator responsible.

\* Date and time.

\* Applicable provider category or service.



New rates should apply to eligible future transactions by default.



Historical transactions must preserve their originally applied rates and calculations.



Any historical correction must use a controlled adjustment process.



\## 9. Service Provider Management Interface



Integrate service provider management into the existing Agile Hub interface.



Provide:



\* A service provider list.

\* Search by provider name, business name, or identifier.

\* Filters for internal and external providers.

\* Filters for active, dormant, suspended, and inactive providers.

\* Provider details.

\* Service assignment.

\* Transaction history.

\* Revenue reports.

\* Commission history.

\* Commission payment history.

\* Outstanding commission balances.

\* Provider activation and suspension.

\* Provider reactivation.



\### Registering an internal provider



The administrator selects an existing Agile Hub member and registers that member as an internal service provider.



The application must reuse the existing member account.



\### Registering an external provider



The administrator enters the external provider's details and registers them as an external service provider.



The application must not require a member account.



Validate each registration according to the selected provider type.



Do not allow an external provider to be accidentally assigned to the internal member relationship.



\## 10. Financial Dashboard



Extend the existing dashboard using actual database data.



\### Revenue



Display:



\* Gross revenue.

\* Returns and refunds.

\* Discounts.

\* Net revenue.



\### Costs and Expenses



Display:



\* Direct service costs.

\* Transportation expenses.

\* Sales expenses.

\* Administrative expenses.

\* Other operating expenses.

\* Total operating expenses.



\### Profit and Commissions



Display:



\* Gross profit.

\* Profit before commission.

\* Total commissions earned.

\* Total commissions paid.

\* Outstanding commissions.

\* Net profit retained by Agile Hub.



\### Service Provider Overview



Display:



\* Total internal service providers.

\* Total external service providers.

\* Active providers.

\* Dormant providers.

\* Suspended providers.

\* Inactive providers.

\* Revenue generated by internal providers.

\* Revenue generated by external providers.

\* Commissions earned by each category.

\* Outstanding payments by provider category.



Include daily, weekly, monthly, and custom date filters.



All dashboard figures must use consistent financial calculations.



Respect existing user permissions.



\## 11. Financial Reports



Implement or extend reports for:



1\. Revenue and returns.

2\. Service costs.

3\. Profitability by service.

4\. Profitability by service provider.

5\. Internal versus external provider performance.

6\. Commission calculations.

7\. Commission payments.

8\. Outstanding commission balances.

9\. Transportation expenses.

10\. Sales expenses.

11\. Administrative expenses.

12\. Dormant service providers.

13\. Financial rate changes and adjustments.



Where the application already supports exporting reports, extend it to the new data.



All reports must use the same calculation logic as the dashboard.



\## 12. Backend and Database Integrity



Follow the existing backend architecture and conventions.



Implement appropriate relationships between:



\* Members and internal service providers.

\* External service providers and their service records.

\* Services and service providers.

\* Service transactions and financial records.

\* Expenses and transactions.

\* Commission records and providers.

\* Commission payments and commission records.

\* Financial settings and audit history.



An external service provider must be able to have service transactions and financial records without a member account.



Use appropriate database constraints and backend validation to enforce the distinction between internal and external providers.



Use database transactions when multiple financial records must be updated together.



Add suitable indexes where needed.



Create safe, reversible migrations and preserve existing data.



\## 13. Security and Permissions



Use the existing authentication and authorization systems.



Only authorized administrators should be able to:



\* Change financial rates.

\* Approve commissions.

\* Record or confirm commission payments.

\* Make financial adjustments.

\* Suspend providers.

\* Modify restricted financial settings.



Enforce permissions on the backend, not only in the frontend.



Do not grant external providers access to member-only features simply because they provide services to the hub.



Record important financial and administrative actions in an audit trail.



\## 14. Testing



Add or update automated tests using the existing testing framework.



Test:



1\. Internal providers must be linked to existing members.

2\. External providers can be registered without member accounts.

3\. Internal and external providers can provide the same eligible services.

4\. Commission calculations work for both provider types.

5\. Different commission rates can be configured for each provider category.

6\. Sales expenses are calculated using the configured 5% default.

7\. Revenue, costs, and profit are calculated correctly.

8\. Transportation expenses and transportation services are handled distinctly.

9\. Refunds and cancellations adjust financial records correctly.

10\. Historical transactions retain their applied rates.

11\. Duplicate commissions and payments are prevented.

12\. Dormant providers are identified correctly.

13\. Financial settings are protected by backend permissions.

14\. Dashboard totals and reports are accurate.

15\. Monetary calculations use appropriate decimal precision.

16\. Existing application functionality remains operational.



Run the relevant existing test suite and fix regressions introduced by the changes.



\## 15. Implementation Rules



\* Work directly in the existing repository.

\* Do not create a replacement application.

\* Do not delete existing features or data.

\* Do not replace the database.

\* Do not create duplicate member accounts.

\* Do not require external providers to become members.

\* Do not hardcode configurable financial rates.

\* Do not use mock data for production financial calculations.

\* Do not silently modify historical financial results.

\* Do not mark commissions as paid without recording payment.

\* Do not expose restricted operations to unauthorized users.

\* Do not leave core features as placeholders.

\* Preserve the application's existing architecture and design conventions.



If an existing implementation conflicts with these requirements, explain the conflict and choose the safest compatible solution.



\## 16. Final Verification



After implementing the changes:



1\. Run backend tests.

2\. Run frontend tests, linting, and type checks where available.

3\. Validate database migrations.

4\. Verify internal and external provider registration.

5\. Verify commission calculations and payments.

6\. Verify the dashboard and financial reports.

7\. Confirm that existing features continue to work.



Finally, provide an implementation summary containing:



\* Files created and modified.

\* Database models and relationships changed.

\* Migrations created.

\* API endpoints added or modified.

\* Frontend pages and components updated.

\* Financial formulas implemented.

\* Tests executed and results.

\* Any manual commands or deployment steps required.

\* Any unresolved issues or assumptions.



Begin by inspecting the existing codebase. Then implement the changes incrementally and verify each major component before proceeding.

