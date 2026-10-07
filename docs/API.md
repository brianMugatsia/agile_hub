# API

The API is mounted at `/api/v1/`. The OpenAPI schema is available through the project schema route, and the documentation UI is restricted to administrators. All API routes require authentication unless explicitly stated otherwise. The default authentication methods are JWT bearer tokens and Django session authentication; global throttles are configured in settings.

## Authentication

Obtain and refresh JWTs using the configured SimpleJWT token endpoints. Send access tokens as:

```http
Authorization: Bearer <access-token>
```

Keep refresh tokens private, use HTTPS, and do not store tokens in URLs or logs. Session-authenticated unsafe requests require CSRF protection.

## Resource routes

Read-only resource routes are grouped under these prefixes:

| Prefix | Resource |
| --- | --- |
| `/hubs/` | Hubs and memberships |
| `/beneficiaries/` | Beneficiary profiles and businesses |
| `/products/` | Products |
| `/inventory/` | Inventory balances and transactions |
| `/sales/` | Sales and sale items |
| `/commissions/` | Agent commissions and settings |
| `/payroll/` | Workers and salary records |
| `/finance/` | Cash-flow and finance records |
| `/notifications/` | User notifications |
| `/audit/` | Audit events |

Resource endpoints support paginated read operations only. They use Django model permissions and role/hub scoping; the API is not an alternative path for bypassing the validated business services.

Sale completion is exposed as a separate authenticated action under the sales API and is permission-checked and transactional. Sales, inventory, commission, and payroll state transitions should be performed through their explicit service-backed actions in the web application; direct writes to these records are not supported.

## Responses and operational notes

Paginated collections use the standard DRF shape (`count`, `next`, `previous`, `results`). Invalid input returns validation errors; permission failures return 403 and unauthenticated requests return 401. Configure paging, token lifetimes, allowed origins, and throttles for the deployment's threat and traffic profile. Review generated schema output after API changes.