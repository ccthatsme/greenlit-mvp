# GreenLit

GreenLit is a platform that helps creators raise funding for YouTube projects, and gives backers transparent visibility into campaign progress and project performance.

## MVP Scope (Current)

- US-first launch
- Creator campaigns with funding goals
- Backer pledges until goal is met
- Funds held until creator publishes deliverable content
- Admin verification before creator payout
- Automatic refunds if publish deadline is missed
- YouTube-based project performance tracking (where available)

## Tech Stack

- Backend: Django + Django REST Framework
- Frontend: React (planned)
- Database: SQLite (local dev), PostgreSQL (planned for production)
- Background jobs: Celery + Redis (planned)
- Payments: Stripe (planned)

## Repository Structure

- `greenlit-backend/` — Django API
- `greenlit-frontend/` — React app (to be added)

## Getting Started (Backend)

1. Create and activate virtual environment
2. Install dependencies from `requirements.txt`
3. Run migrations
4. Start the dev server

Example commands (PowerShell):

- `cd greenlit-backend`
- `.\venv\Scripts\Activate.ps1`
- `pip install -r requirements.txt`
- `python manage.py migrate`
- `python manage.py runserver`

## Environment Variables

Create a local `.env` file in `greenlit-backend/` using `.env.example` as a template.

## Current Status

- Django backend scaffold initialized
- Initial app structure in progress
- Auth/roles and campaign domain modeling next

## Roadmap (High Level)

1. Auth + role-based access (backer, creator, admin)
2. Creator profile + YouTube connection
3. Campaign creation + funding flow
4. Stripe integration + webhook handling
5. Publish verification + disbursement/refund workflows
6. Backer dashboard and performance reporting

## Notes

This project is in active MVP development. Product and technical decisions are intentionally iterative.