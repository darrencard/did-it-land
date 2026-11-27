# Did it land? Acme, read 2026-11-26

*Illustrative: every figure here is sample data.*

1 landed, 5 watch, 1 stalled, 0 not read.

| Bet | Status | Metric | Now | Bar, by | Source |
|---|---|---|---|---|---|
| Quote drafting | **landed** | Quote draft acceptance rate | 43% (2026-11-23) | 40%, 2026-11-15 | Illustrative product analytics export, quote_drafts_weekly.csv |
| Invoice chasing | **watch** | Days sales outstanding | 35 (2026-11-23) | 30, 2026-12-31 | Illustrative finance export, dso_weekly.csv |
| Job scheduler | **stalled** | Weekly active schedulers | 2,100 (2026-11-23) | 3,000, 2026-10-31 | Illustrative product analytics export, scheduler_wau.csv |
| Payment links | **watch** | Payment link conversion | 18.1% (2026-11-23) | 18%, 2026-11-30 | Illustrative billing export, payment_links_weekly.csv |
| Automatic reminders | **watch** | Reminders sent per week | 24,000 (2026-11-23) | 20,000, 2026-11-30 | Illustrative messaging log export, reminders_weekly.csv |
| SMS reminders | **watch** | Reminder open rate | 58% (2026-11-09) | 55%, 2026-12-15 | Illustrative messaging log export, reminder_opens_weekly.csv |
| Auto match | **watch** | Invoice auto-match rate | 95% (2026-11-23) | 80%, 2026-12-31 | Illustrative reconciliation export, auto_match_weekly.csv |

## Quote drafting: landed

- **landed**. Past the bar of 40% by 2026-11-15. Cost: over budget, cited from cost-budget-check 0.3.1.
- Quote draft acceptance rate is 43% on 2026-11-23, against a bar of 40% (higher is better) by 2026-11-15. At the date it read 41% (2026-11-09). Source: Illustrative product analytics export, quote_drafts_weekly.csv.
- Since launch on 2026-09-07: pre-launch mean 21.67% over 6 readings, then 41%, a move of +19.33, 5.05 times the pre-launch spread (3.83).
- Outcome, Quote win rate: 31 to 36 over the same window (7 readings). Source: Illustrative CRM export, quotes_won_weekly.csv.
- Cost check, cited from the loop record: over budget (cost-budget-check 0.3.1, 2026-11-01 to 2026-11-14): cost per task $0.0338 against $0.027, 25% over; tokens per task 10,300 against 9,000, 14% over; price per token $0.00000328 against $0.000003, 9% over.
- Flag, over-cost-budget: Cost is over budget, cited from cost-budget-check 0.3.1. It does not change the status.
- Next step: Keep the metric on the scorecard, and decide whether to scale the bet, given cost is over budget. Decides: Head of Product, Quoting squad. Due: 2026-12-10.

## Invoice chasing: watch

- **watch**. Not there yet, moving the right way since the last reading (36), and 2026-12-31 has not passed.
- Days sales outstanding is 35 on 2026-11-23, against a bar of 30 (lower is better) by 2026-12-31. Source: Illustrative finance export, dso_weekly.csv.
- Since launch on 2026-10-05: pre-launch mean 40.6 over 5 readings, then 35, a move of -5.6, 10.22 times the pre-launch spread (0.55).
- Next step: Read again at the next reading, and by 2026-12-31 at the latest. Decides: Head of Product, Payments squad. Due: 2026-12-31.

## Job scheduler: stalled

- **stalled**. The date, 2026-10-31, has passed and the metric did not reach the bar of 3,000.
- Weekly active schedulers is 2,100 on 2026-11-23, against a bar of 3,000 (higher is better) by 2026-10-31. At the date it read 2,110 (2026-10-26). Source: Illustrative product analytics export, scheduler_wau.csv.
- Since launch on 2026-08-03: pre-launch mean 2,060 over 4 readings, then 2,110, a move of +50, 2.74 times the pre-launch spread (18.26).
- Flag, thin-baseline: The pre-launch spread comes from 4 readings, so the noise band itself is rough. Weigh the noise call lightly.
- Flag, green-over-red: The tracker shows this bet green while the read is stalled.
- Next step: Decide one of three: change course, write a new brief with a new bar and date, or stop the bet. Correct the status shown in the tracker. Decides: Head of Product, Field squad. Due: 2026-12-10.

## Payment links: watch

- **watch**. Past the bar of 18%, but the call is held: within-noise.
- Payment link conversion is 18.1% on 2026-11-23, against a bar of 18% (higher is better) by 2026-11-30. Source: Illustrative billing export, payment_links_weekly.csv.
- Since launch on 2026-10-19: pre-launch mean 16.92% over 6 readings, then 18.1%, a move of +1.18, 1.48 times the pre-launch spread (0.8).
- Flag, within-noise: 18.1% is 1.48 times the pre-launch spread (0.8) from the pre-launch mean (16.92%), under the 2 needed. Within noise: run an experiment.
- Flag, one-step-rosier: The tracker shows this bet green while the read is watch.
- Next step: Run an experiment before calling it: hold the bet back from a random group and compare Payment link conversion between the two groups. Correct the status shown in the tracker. Decides: Head of Product, Payments squad. Due: 2026-11-30.

## Automatic reminders: watch

- **watch**. Past the bar of 20,000, but the call is held: metric-up-outcome-down.
- Reminders sent per week is 24,000 on 2026-11-23, against a bar of 20,000 (higher is better) by 2026-11-30. Source: Illustrative messaging log export, reminders_weekly.csv.
- Since launch on 2026-09-21: pre-launch mean 8,000 over 4 readings, then 24,000, a move of +16000, 175.27 times the pre-launch spread (91.29).
- Outcome, Invoices paid within 14 days: 62 to 58 over the same window (6 readings). Source: Illustrative finance export, paid_14d_weekly.csv.
- Flag, thin-baseline: The pre-launch spread comes from 4 readings, so the noise band itself is rough. Weigh the noise call lightly.
- Flag, metric-up-outcome-down: Reminders sent per week improved while Invoices paid within 14 days moved the wrong way (62 to 58). The number is improving and the result is not.
- Flag, green-over-red: The tracker shows this bet green while the read is watch and its outcome is moving the wrong way.
- Next step: Check whether the metric still tracks the outcome before crediting it. Correct the status shown in the tracker. Decides: Head of Product, Payments squad. Due: 2026-11-30.

## SMS reminders: watch

- **watch**. Past the bar of 55%, but the call is held: source-stale.
- Reminder open rate is 58% on 2026-11-09, against a bar of 55% (higher is better) by 2026-12-15. Source: Illustrative messaging log export, reminder_opens_weekly.csv.
- Since launch on 2026-09-28: pre-launch mean 41% over 4 readings, then 58%, a move of +17, 20.82 times the pre-launch spread (0.82).
- Flag, source-stale: No fresh reading in 289h (the limit is 48h). A stale source reads as health it has not earned.
- Flag, thin-baseline: The pre-launch spread comes from 4 readings, so the noise band itself is rough. Weigh the noise call lightly.
- Flag, one-step-rosier: The tracker shows this bet green while the read is watch.
- Next step: Fix or verify the source, then read again. If a jump is real, record who checked it in verified_jumps. Correct the status shown in the tracker. Decides: Head of Product, Messaging squad. Due: 2026-12-15.

## Auto match: watch

- **watch**. Past the bar of 80%, but the call is held: source-jumpy.
- Invoice auto-match rate is 95% on 2026-11-23, against a bar of 80% (higher is better) by 2026-12-31. Source: Illustrative reconciliation export, auto_match_weekly.csv.
- Since launch on 2026-10-05: pre-launch mean 61.5% over 4 readings, then 95%, a move of +33.5, 58.02 times the pre-launch spread (0.58).
- Flag, source-jumpy: The latest step (30) is more than 5 times this source's usual step (1). Verify the source before trusting it.
- Flag, thin-baseline: The pre-launch spread comes from 4 readings, so the noise band itself is rough. Weigh the noise call lightly.
- Next step: Fix or verify the source, then read again. If a jump is real, record who checked it in verified_jumps. Decides: Head of Product, Ledger squad. Due: 2026-12-31.

A metric moving is not proof that the bet moved it. This read says whether the metric reached the bar, not why.
