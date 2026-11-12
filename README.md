# RailFlow — Train Booking System

A new Django-based implementation of **Design and Implementation of a Web-Based Train Booking System**.

Stack: Python, Django, PostgreSQL, Django templates, CSS, HTMX, pytest.

Development happens on `development`; the default branch is reserved for reviewed releases.

## Paystack test checkout

Passenger checkout uses Paystack's hosted **test mode**; no live payments are accepted.
See [test-mode setup, verification and refund limitations](docs/paystack-test-checkout.md).
Set `PAYSTACK_TEST_SECRET_KEY` privately in `.env`, run migrations, and use the
Paystack option in My bookings. The old wallet service remains for existing data
but is no longer the visible passenger checkout.
