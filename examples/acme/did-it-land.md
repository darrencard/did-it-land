# Did it land? Acme, read 2026-11-26

*Illustrative: every figure here is sample data.*

1 landed, 5 watch, 1 stalled, 0 not read.

The scorecard: one row per project, its average before launch, the latest reading and the target.

| Project | Before launch → now · target | Status |
|---|---|---|
| Quote drafting | 22% → **43%** · TARGET 40% | **landed**, cost over budget |
| Invoice chasing | 41 → **35** · TARGET 30 · LOWER IS BETTER | **watch** |
| Job scheduler | 2,060 → **2,100** · TARGET 3,000 | **stalled** |
| Payment links | 16.9% → **18.1%** · TARGET 18% | **watch**, past target · inside normal ups and downs |
| Automatic reminders | 8,000 → **24,000** · TARGET 20,000 | **watch**, past target · outcome fell |
| SMS reminders | 41% → **58%** · TARGET 55% | **watch**, past target · data out of date |
| Auto match | 62% → **95%** · TARGET 80% | **watch**, past target · data jumped |

## Quote drafting: landed

- **landed**. Past the target of 40% by 2026-11-15. Cost: over budget, from the cost check.
- Quote draft acceptance rate is 43% on 2026-11-23, against a target of 40% or higher by 2026-11-15. On the due date it read 41% (2026-11-09). Source: Illustrative product analytics export, quote_drafts_weekly.csv.
- Since launch on 2026-09-07: from an average of 21.67% over 6 readings before launch to 41%, a move of +19.33, 5.05 times its usual ups and downs before launch.
- The result it should drive, Quote win rate: 31 to 36 over the same weeks (7 readings). Source: Illustrative CRM export, quotes_won_weekly.csv.
- The cost check, from the project file: over budget (cost-budget-check 0.3.3, 2026-11-01 to 2026-11-14): cost per task $0.0338 against $0.027, 25% over; AI usage per task 10,300 against 9,000, 14% over; AI price per unit $0.00000328 against $0.000003, 9% over.
- Check: Cost is over budget, from the cost check. It never changes the status.
- Next step: Keep the number on the scorecard, and decide whether to scale the project, given cost is over budget. Decides: Head of Product, Quoting squad. Due: 2026-12-10.

## Invoice chasing: watch

- **watch**. Not there yet, moving the right way since the last reading (36), and 2026-12-31 has not passed.
- Days sales outstanding is 35 on 2026-11-23, against a target of 30 or lower by 2026-12-31. Source: Illustrative finance export, dso_weekly.csv.
- Since launch on 2026-10-05: from an average of 40.6 over 5 readings before launch to 35, a move of -5.6, 10.22 times its usual ups and downs before launch.
- Next step: Read again at the next reading, and by 2026-12-31 at the latest. Decides: Head of Product, Payments squad. Due: 2026-12-31.

## Job scheduler: stalled

- **stalled**. The date, 2026-10-31, has passed and the number did not reach the target of 3,000.
- Weekly active schedulers is 2,100 on 2026-11-23, against a target of 3,000 or higher by 2026-10-31. On the due date it read 2,110 (2026-10-26). Source: Illustrative product analytics export, scheduler_wau.csv.
- Since launch on 2026-08-03: from an average of 2,060 over 4 readings before launch to 2,110, a move of +50, 2.74 times its usual ups and downs before launch.
- Check: Only a few readings came before launch, so its usual range is a rough guess.
- Check: The tracker shows this project green, which is rosier than this read.
- Next step: Decide one of three: change course, write a new landing brief with a new target and date, or stop the project. Correct the status shown in the tracker. Decides: Head of Product, Field squad. Due: 2026-12-10.

## Payment links: watch

- **watch**. Past the target of 18%, but inside normal ups and downs.
- Payment link conversion is 18.1% on 2026-11-23, against a target of 18% or higher by 2026-11-30. Source: Illustrative billing export, payment_links_weekly.csv.
- Since launch on 2026-10-19: from an average of 16.92% over 6 readings before launch to 18.1%, a move of +1.18, 1.48 times its usual ups and downs before launch.
- Check: Inside normal ups and downs: since launch the number sits inside the ups and downs it had before launch.
- Check: The tracker shows this project green, one step rosier than this read.
- Next step: Run an experiment before calling it: hold the project back from a random group and compare Payment link conversion between the two groups. Correct the status shown in the tracker. Decides: Head of Product, Payments squad. Due: 2026-11-30.

## Automatic reminders: watch

- **watch**. Past the target of 20,000, but not called yet: the result it should drive fell.
- Reminders sent per week is 24,000 on 2026-11-23, against a target of 20,000 or higher by 2026-11-30. Source: Illustrative messaging log export, reminders_weekly.csv.
- Since launch on 2026-09-21: from an average of 8,000 over 4 readings before launch to 24,000, a move of +16000, 175.27 times its usual ups and downs before launch.
- The result it should drive, Invoices paid within 14 days: 62 to 58 over the same weeks (6 readings). Source: Illustrative finance export, paid_14d_weekly.csv.
- Check: Only a few readings came before launch, so its usual range is a rough guess.
- Check: The number rose, but the result it should drive fell.
- Check: The tracker shows this project green, which is rosier than this read.
- Next step: Check whether the number still tracks the outcome before crediting it. Correct the status shown in the tracker. Decides: Head of Product, Payments squad. Due: 2026-11-30.

## SMS reminders: watch

- **watch**. Past the target of 55%, but not called yet: the data source is out of date.
- Reminder open rate is 58% on 2026-11-09, against a target of 55% or higher by 2026-12-15. Source: Illustrative messaging log export, reminder_opens_weekly.csv.
- Since launch on 2026-09-28: from an average of 41% over 4 readings before launch to 58%, a move of +17, 20.82 times its usual ups and downs before launch.
- Check: The data source is out of date, so the read cannot trust the last reading.
- Check: Only a few readings came before launch, so its usual range is a rough guess.
- Check: The tracker shows this project green, one step rosier than this read.
- Next step: Fix or verify the data source, then read again. If the jump is real, note who checked it. Correct the status shown in the tracker. Decides: Head of Product, Messaging squad. Due: 2026-12-15.

## Auto match: watch

- **watch**. Past the target of 80%, but not called yet: the data source jumped.
- Invoice auto-match rate is 95% on 2026-11-23, against a target of 80% or higher by 2026-12-31. Source: Illustrative reconciliation export, auto_match_weekly.csv.
- Since launch on 2026-10-05: from an average of 61.5% over 4 readings before launch to 95%, a move of +33.5, 58.02 times its usual ups and downs before launch.
- Check: The last reading jumped far more than this source usually moves. Check the source before trusting it.
- Check: Only a few readings came before launch, so its usual range is a rough guess.
- Next step: Fix or verify the data source, then read again. If the jump is real, note who checked it. Decides: Head of Product, Ledger squad. Due: 2026-12-31.

A number moving is not proof that the project moved it. This read says whether the number reached the target, not why.

## For your engineers

| Project | Status | Flag codes | Landing brief | Slug |
|---|---|---|---|---|
| Quote drafting | landed | `over-cost-budget` | quote-drafting.md | `quote-drafting` |
| Invoice chasing | watch | none | invoice-chasing.md | `invoice-chasing` |
| Job scheduler | stalled | `thin-baseline`, `green-over-red` | job-scheduler.md | `job-scheduler` |
| Payment links | watch | `within-noise`, `one-step-rosier` | payment-links.md | `payment-links` |
| Automatic reminders | watch | `thin-baseline`, `metric-up-outcome-down`, `green-over-red` | automatic-reminders.md | `automatic-reminders` |
| SMS reminders | watch | `source-stale`, `thin-baseline`, `one-step-rosier` | sms-reminders.md | `sms-reminders` |
| Auto match | watch | `source-jumpy`, `thin-baseline` | auto-match.md | `auto-match` |

Quote drafting: the cost word is cited from `cost-budget-check 0.3.3`; the read never recomputes it.

With --loop and --bet, the read adds its page to the project file: the `landed` key of `landing/<slug>.json`, and no other key. Built by did-it-land 0.3.5.
