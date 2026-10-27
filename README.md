# Kasra Publishing — Django E-commerce Platform

A Django-based web application for **Kasra Publishing**, a specialized publisher and bookstore focused on architecture, urbanism, interior design, and art.

The project aims to provide a Persian (Farsi), right-to-left (RTL) online bookstore while preserving important business workflows and supporting a reliable transition from the existing WordPress/WooCommerce platform.

> **Project status:** In development. Not approved for production deployment.

## Project Goals

- Build a maintainable e-commerce platform using Django.
- Provide a Persian-language, right-to-left user experience.
- Support the catalog and sales workflows of a specialized publishing business.
- Preserve historical order and payment records during migration.
- Maintain existing website URLs and support SEO continuity.
- Implement secure payment and order-processing workflows.
- Provide functional user interfaces rather than decorative, non-functional controls.

## Technology Stack

The project is built around Django and Python.

The technology stack, dependencies, database configuration, payment integrations, and deployment architecture should be verified against the current repository before production use.

## Core Requirements

### E-commerce
- Product catalog and book details
- Product categories and browsing
- Shopping cart and checkout
- Order management
- Shipping and payment workflows

### Localization and Accessibility
- Persian (Farsi) language support
- Right-to-left (RTL) layout
- Consistent typography and navigation
- Responsive user interface

### Migration and Data Integrity
- Careful migration from WordPress/WooCommerce
- Preservation and verification of historical orders
- Validation of payment records
- Protection of existing customer and business data
- Compatibility with existing URLs where required

### Security and Deployment
- Secure management of secrets and environment variables
- Payment verification and order-state validation
- Production-ready HTTPS and server configuration
- Database backup and recovery procedures
- Testing before production release

*The items above describe project goals and requirements; they should not be interpreted as confirmation that every feature has been implemented.*

## Development Status

This project is undergoing development and technical review.

Production deployment and historical order corrections remain **on hold** until the relevant security, data-integrity, payment, migration, and operational checks have been completed and approved.

No production-readiness claim is made by this repository overview.

## Getting Started

The following is a general outline. Exact commands and configuration depend on the current repository structure.

### Prerequisites

- Python compatible with the project's dependency configuration
- Git
- A database supported by the application
- A virtual environment

### Setup

Clone the repository:

```bash
git clone https://github.com/maryamardom-bit/books.git
cd books
```

Create and activate a virtual environment.

On Windows:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Install the project's dependencies using its existing dependency file, if available. For example:

```bash
pip install -r requirements.txt
```

Configure the required environment variables using the project's configuration instructions. Never commit real credentials, secret keys, payment tokens, or production database information.

Before running migrations or starting the application, inspect the project's settings and database configuration.

The exact commands for migrations, tests, and local development should be documented after verifying the current project structure.

## Configuration and Secrets

Sensitive configuration must be provided through environment variables or an appropriate secrets-management system.

Do not commit:

- Production credentials or secret keys
- Database passwords or private connection strings
- Payment gateway secrets
- Customer personal information
- Database backups or private exports

Use a safe example configuration file when documenting required environment variables.

## Testing and Quality Assurance

Before release, the project should be checked for:

- Application and model correctness
- Authentication and authorization
- Checkout and payment verification
- Order-state consistency
- Migration integrity
- Regression issues
- Security misconfigurations
- Deployment and recovery readiness

Only verified test results should be reported as passing.

## Contributing

Contributions and technical feedback are welcome.

Before submitting changes:

1. Review the existing code and project conventions.
2. Keep credentials and private data out of commits.
3. Add or update tests for relevant changes.
4. Document configuration or migration changes.
5. Avoid making production or historical-data changes without explicit authorization.

## License

No license has been specified yet. Unless a license is added to the repository, do not assume that the code is available for unrestricted reuse, redistribution, or modification.

## Project Website

[Kasra Publishing](https://kasrapublishing.ir/)

