# Qwen electricity-only cost receipt — 2026-10-29

This receipt records a dated electricity-rate calculation for `un/qwen3.8-27b-gguf`. It is partial operating-cost evidence only; it does not complete Issue #2 or change the catalog cost policy in [architecture](architecture.md#cost-schema).

## Inputs and provenance

- **Power draw:** 335 W gross, owner-reported for 2026-10-29; not independently verified here. Gross draw is not an incremental/inference-only measurement.
- **Electricity tariff:** 8.46 RUB/kWh, owner-accepted for this calculation; not independently verified here.
- **USD exchange rate:** 80.8664 RUB/USD, the Central Bank of Russia daily rate for 2026-10-29. [Official CBR daily rates](https://www.cbr.ru/scripts/XML_daily.asp?date_req=29/10/2026), retrieved 2026-10-29 at 23:47:24 UTC. This is a dated published rate, not a new live FX lookup.

## Calculation

Convert the reported gross draw to kilowatts, multiply by the accepted tariff, and divide by the dated USD rate:

```text
0.335 kW × 8.46 RUB/kWh ÷ 80.8664 RUB/USD
= 0.03504669430072316808958974308 USD/hour
≈ 0.03505 USD/hour
```

Units reduce to USD/hour. The result is an **electricity-only rate** based on the stated gross draw and tariff. It is not incremental power, idle-adjusted cost, full operating cost, or token cost.

## Cost-policy status

The result does not establish cost per token or per million tokens. Throughput and hardware amortization evidence required for full local operating cost remains unmet under Issue #2, which remains closed. Accordingly, `localCostPerMillion` for this Qwen entry remains `null`; no catalog or client-template cost value is set by this receipt.
