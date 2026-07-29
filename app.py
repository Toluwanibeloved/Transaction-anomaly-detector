import streamlit as st
import pandas as pd
import numpy as np
import json
import os


class TransactionAnomalyDetector:
    def __init__(self, threshold=2.0):
        self.threshold = threshold
        self.mean_log = None
        self.std_log = None

    def fit(self, debit_amounts):
        log_amounts = np.log(debit_amounts)
        self.mean_log = log_amounts.mean()
        self.std_log = log_amounts.std()

    def score(self, amount):
        log_amount = np.log(amount)
        z_score = (log_amount - self.mean_log) / self.std_log
        is_anomaly = z_score > self.threshold
        return z_score, is_anomaly

    def spending_max(self):
        return np.exp(self.mean_log + self.threshold * self.std_log)


def clean_transactions(raw_df):
    expected_columns = {"Value Date", "Debit (NGN)"}
    missing = expected_columns - set(raw_df.columns)
    if missing:
        raise ValueError(
            f"Missing column(s): {', '.join(missing)}. "
            f"Found these columns instead: {', '.join(raw_df.columns)}"
        )

    df = raw_df.rename(columns={
        "Value Date": "date",
        "Debit (NGN)": "debit_transactions"
    })

    df["debit_transactions"] = pd.to_numeric(df["debit_transactions"], errors="coerce")
    if df["debit_transactions"].isna().any():
        raise ValueError(
            "Some rows in the 'Debit (NGN)' column aren't valid numbers. "
            "Check for blank cells or text mixed into that column."
        )
    df["debit_transactions"] = df["debit_transactions"].abs()

    df["date"] = pd.to_datetime(df["date"], format="%d/%m/%Y", errors="coerce")
    if df["date"].isna().any():
        raise ValueError(
            "Some dates couldn't be read. Make sure dates are in DD/MM/YYYY format, e.g. 02/03/2026."
        )

    if len(df) == 0:
        raise ValueError("This file has no transaction rows to analyze.")

    return df


def customer_message(flagged):
    if flagged:
        return "⚠️ This transaction is unusual based on your normal spending pattern."
    else:
        return "✅ Transaction approved."


NO_HISTORY_MESSAGE = "No spending history loaded yet. Upload your transactions at the Internal View tab."
MINIMUM_DAYS_REQUIRED = 90

# Files we save to, so data survives a restart
TRANSACTIONS_FILE = "saved_transactions.csv"
DETECTOR_STATE_FILE = "saved_detector_state.json"
LOG_FILE = "saved_transaction_log.csv"


def reset_all_data():
    for path in [TRANSACTIONS_FILE, DETECTOR_STATE_FILE, LOG_FILE]:
        if os.path.exists(path):
            os.remove(path)

    for key in ["detector", "transactions_df", "enough_history"]:
        if key in st.session_state:
            del st.session_state[key]

    st.session_state["transaction_log"] = []


# --- Load saved data from disk, but only on a fresh session ---
if "detector" not in st.session_state and os.path.exists(DETECTOR_STATE_FILE) and os.path.exists(TRANSACTIONS_FILE):
    with open(DETECTOR_STATE_FILE, "r") as f:
        saved_state = json.load(f)

    detector = TransactionAnomalyDetector(threshold=saved_state["threshold"])
    detector.mean_log = saved_state["mean_log"]
    detector.std_log = saved_state["std_log"]

    st.session_state["detector"] = detector
    st.session_state["transactions_df"] = pd.read_csv(TRANSACTIONS_FILE, parse_dates=["date"])
    st.session_state["enough_history"] = saved_state["enough_history"]

if "transaction_log" not in st.session_state:
    if os.path.exists(LOG_FILE):
        st.session_state["transaction_log"] = pd.read_csv(LOG_FILE).to_dict("records")
    else:
        st.session_state["transaction_log"] = []


st.title("Transaction Analyst & Anomaly Detector")

customer_tab, insights_tab, staff_tab = st.tabs(
    ["Transfer View", "My Spending Analysis", "Internal View"]
)

with staff_tab:
    st.header("Internal: Upload & Review")

    if st.button("🗑️ Clear all saved data"):
        reset_all_data()
        st.success("All data cleared. Upload a new file to start fresh.")

    st.caption(
        "Your CSV must contain exactly two columns with these exact column names: **Value Date** (format DD/MM/YYYY) "
        "and **Debit (NGN)** (transaction amounts)."
    )

    uploaded_file = st.file_uploader("Upload your transaction CSV", type="csv")

    if uploaded_file is not None:
        try:
            raw_df = pd.read_csv(uploaded_file)
            df = clean_transactions(raw_df)
        except ValueError as e:
            st.error(f"⚠️ Couldn't process this file: {e}")
        except Exception:
            st.error("⚠️ Something went wrong reading this file. Please check it's a valid CSV export.")
        else:
            date_span_days = (df["date"].max() - df["date"].min()).days
            enough_history = date_span_days >= MINIMUM_DAYS_REQUIRED

            detector = TransactionAnomalyDetector(threshold=2.0)
            detector.fit(df["debit_transactions"])

            z_scores, flags = detector.score(df["debit_transactions"])
            df["z_score"] = z_scores
            df["flagged"] = flags

            st.session_state["detector"] = detector
            st.session_state["transactions_df"] = df
            st.session_state["enough_history"] = enough_history

            # Save to disk so this survives an app restart
            df.to_csv(TRANSACTIONS_FILE, index=False)
            with open(DETECTOR_STATE_FILE, "w") as f:
                json.dump({
                    "mean_log": float(detector.mean_log),
                    "std_log": float(detector.std_log),
                    "threshold": float(detector.threshold),
                    "enough_history": bool(enough_history)
                }, f)

            st.write(f"Data covers **{date_span_days} days**.")
            if not enough_history:
                st.warning(
                    f"This is under the {MINIMUM_DAYS_REQUIRED}-day minimum — "
                    "Anomaly dectector and anaylst will stay hidden until there's enough history. "
                )

            st.write("All transactions, scored:")
            st.dataframe(df)
            st.write("Flagged as unusual:")
            st.dataframe(df[df["flagged"]])

    st.write("---")
    st.subheader("Live activity log")
    if len(st.session_state["transaction_log"]) == 0:
        st.write("No checks yet.")
    else:
        log_df = pd.DataFrame(st.session_state["transaction_log"])
        st.dataframe(log_df)


def history_ready():
    return "detector" in st.session_state and st.session_state.get("enough_history", False)


with customer_tab:
    st.header("Check a Transaction")

    if not history_ready():
        st.info(NO_HISTORY_MESSAGE)
    else:
        detector = st.session_state["detector"]
        amount = st.number_input("Enter a transaction amount (₦)", min_value=0.0, step=100.0)

        if st.button("Check transaction"):
            z, flagged = detector.score(amount)
            st.subheader(customer_message(flagged))

            st.session_state["transaction_log"].append({
                "amount": amount,
                "z_score": z,
                "flagged": flagged
            })

            # Save the log too, so it survives a restart
            pd.DataFrame(st.session_state["transaction_log"]).to_csv(LOG_FILE, index=False)

with insights_tab:
    st.header("My Spending Analysis")

    if not history_ready():
        st.info(NO_HISTORY_MESSAGE)
    else:
        detector = st.session_state["detector"]
        df = st.session_state["transactions_df"]

        spending_max = detector.spending_max()
        average_mean = df["debit_transactions"].mean()
        average_median = df["debit_transactions"].median()

        col1, col2, col3 = st.columns(3)
        col1.metric(
            "Average spending (mean)", f"₦{average_mean:,.2f}",
            help="Adds up all your transactions and divides by how many there are. One unusually large transaction can pull this number higher than what you typically spend."
        )
        col2.metric(
            "Typical spending (median)", f"₦{average_median:,.2f}",
            help="Your true middle transaction once everything is sorted smallest to largest. Less thrown off by one big outlier."
        )
        col3.metric(
            "Your spending max", f"₦{spending_max:,.2f}",
            help="Transactions above this amount are unusual for your pattern."
        )

        st.subheader("Your spending over time")
        chart_df = df.set_index("date")[["debit_transactions"]].rename(
            columns={"debit_transactions": "Your spending"}
        )
        chart_df["Your spending max"] = spending_max
        st.line_chart(chart_df)

        st.subheader("Transactions above your spending max")
        above_max = df[df["debit_transactions"] > spending_max][["date", "debit_transactions"]]
        above_max = above_max.rename(columns={"date": "Date", "debit_transactions": "Amount (₦)"})

        if len(above_max) == 0:
            st.write("None yet — all your past transactions have stayed within your usual range.")
        else:
            st.dataframe(above_max)
