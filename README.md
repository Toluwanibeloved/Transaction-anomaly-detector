# Transaction Analyst & Anomaly Detector

A proof-of-concept web app that learns a customer's normal spending pattern from their transaction history and flags unusually large transactions — with a customer-friendly interface, a internal review view, and a personal spending analytics dashboard.

🔗 **Live app:** https://belovedguard-analytics.streamlit.app

## What it does

- Learns each customer's typical spending behavior from their debit transaction history
- Gives customers their own spending insights: average spending, typical spending, a "spending max" threshold, and a chart of spending over time
- Flags transactions that are statistically unusual for that specific customer
- Requires a minimum of 3 months of transaction history before activating insights or detection, so the baseline isn't built on too little data
- Shows customers a plain-language alert rather than technical statistics
- Gives the internal tab the full technical detail — z-scores, flagged transactions, and a live log of customer-facing checks
- Handles messy or malformed CSV uploads gracefully, with clear error messages instead of crashes
- Saves data to disk so it survives an app restart, with a one-click reset for testing

## How the detection works

Transaction amounts are log-transformed (to correct for right-skewed spending data), then converted to Z-scores against the customer's own historical mean and standard deviation. A transaction is flagged if it falls more than 2 standard deviations above the customer's typical (log-transformed) spending.

## Expected CSV format

Your file must contain exactly these two column headers:

| Column name | Description | Example |
|---|---|---|
| `Value Date` | Transaction date, in DD/MM/YYYY format | 02/03/2026 |
| `Debit (NGN)` | Transaction amount (positive or negative — sign is ignored) | 2500.00 |

Other columns in your file are fine and will be ignored. If your file uses different column names, rename them to match before uploading.

## Scope & limitations

This is a proof-of-concept for **one detection signal** — unusual transaction *amount* — built as a personal learning project. It is not a production fraud engine. A real banking fraud system would combine this kind of signal with others (location, time, device, transaction velocity, merchant category), use a labeled feedback loop to improve over time, and run as a backend service integrated with a bank's core transaction systems rather than a manually-uploaded CSV.

## Built with

Python, Streamlit, pandas, NumPy

## Run it locally

```bash
pip install -r requirements.txt
streamlit run app.py
```
