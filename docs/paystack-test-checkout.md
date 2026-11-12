# Paystack test checkout for RailFlow

This branch integrates Paystack's hosted **test-mode** checkout for held train seats.
It does not accept live payments, and test transactions do not transfer money.

## Setup

1. Create a Paystack account and open its **test** API keys.
2. Set `PAYSTACK_TEST_SECRET_KEY=sk_test_...` in the local `.env` file.
   Never commit this file or paste the key in chat. Live keys (`sk_live_`) are rejected.
3. Optionally set `PAYSTACK_WEBHOOK_SECRET=whsec_...` if Paystack provides the
   newer timestamped signing secret. Otherwise the legacy test-key signature is accepted.
4. Run `python manage.py migrate`, then `python manage.py runserver`.
5. Register a passenger, provide an email in My profile, and complete staff
   identity-document review. Reserve a seat and choose Paystack from My bookings.
6. Complete payment with a Paystack test payment method. Django verifies the
   transaction before confirming a ticket.

The webhook endpoint is `/payments/paystack/webhook/`. Paystack cannot reach a
localhost URL: use a public HTTPS staging URL or an HTTPS tunnel for webhook tests.
The callback endpoint is `/payments/paystack/callback/`.

## Safety and limitations

- The system checks the reference, currency, amount (kobo), test domain and
  provider status before confirming a ticket.
- A 10-minute seat hold is **not extended** while the passenger is on checkout.
  A successful payment after expiry is flagged **Needs review**, not fulfilled.
- Duplicate callbacks and webhooks cannot confirm a booking twice.
- Paystack cancellation and operator-cancellation refunds are recorded as
  **Refund pending** for manual staff review; they are **not automatically sent**
  to Paystack and **never** credited to the demo wallet.
- The legacy wallet service remains for compatibility with existing records and
  tests, but it is no longer shown as the passenger checkout method.
- The local demo seeding command is still available for safe sample schedules.
  Sample train data is not a claim of connection to a railway operator.
- Do not enable live keys or sell tickets without authorization, complete refund
  reconciliation, operational controls and appropriate security testing.

## Test

Run `python manage.py makemigrations --check --dry-run`,
`python manage.py check`, and `python manage.py test`.
Payment tests mock Paystack API calls; test keys are not required for CI.
