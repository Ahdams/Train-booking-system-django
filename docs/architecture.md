# Phase 2 — RailFlow data architecture

Django renders pages on the server. PostgreSQL is the intended production database; SQLite is allowed for local development and initial CI.

## Relationships

- Station → Route (origin and destination)
- Route + Train → Schedule (recurring timetable)
- Train → Coach → Seat (physical seat inventory)
- Schedule + Travel Date + Seat → Booking (a dated reservation)
- Schedule + Travel Class → Fare (NGN)
- User → Booking, Wallet, PassengerReport
- Wallet → WalletTransaction

## Booking invariants

The database enforces at most one **held or confirmed** booking for a seat on a given schedule and travel date. A cancelled or expired booking frees the seat. Booking operations must run in `transaction.atomic()`, and the application must catch `IntegrityError` for concurrent attempts. A held booking does **not** automatically expire when its timestamp passes: a background job or explicit expiry transaction must set its status to `expired` first.

Application validation must also verify that a selected seat belongs to the train assigned to the schedule, that the schedule operates on the requested weekday, and that the travel date is not in the past. Wallet balance changes and ledger entries must be committed together under a row lock. Never accept client-supplied ticket prices or wallet balances.

## Next phase

Create and commit Django migrations, implement the registration/login experience, add server-side train search and seat reservation services, then test on PostgreSQL for concurrency behavior.
