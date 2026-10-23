import os
from datetime import date, datetime
import pandas as pd
import io
import requests

# Set working directory to the script's location
os.chdir(os.path.dirname(os.path.abspath(__file__)))

NIKKEI_CSV_URL = "https://indexes.nikkei.co.jp/nkave/archives/file/nikkei_stock_average_weight_en.csv"


def load_nikkei_constituents():
    """
    Fetch Nikkei 225 weight CSV and return the full DataFrame
    with all original columns preserved.
    """
    header = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.75 Safari/537.36"
    }

    r = requests.get(NIKKEI_CSV_URL, headers=header, timeout=30)
    r.raise_for_status()

    df = pd.read_csv(io.StringIO(r.text), skipfooter=1, engine='python')

    # Normalize column names (strip whitespace)
    df.columns = [c.strip() for c in df.columns]

    if "Code" not in df.columns:
        raise ValueError(f"Expected 'Code' column not found. Columns: {df.columns.tolist()}")

    df["Code"] = df["Code"].astype(str).str.strip()
    df = df[df["Code"] != ""]

    return df


def create_constituents(df):
    """
    Create a single-row DataFrame with today's date and
    a comma-separated list of all tickers.
    """
    # Use 'ticker' column since we already renamed it
    ticker_list = df["ticker"].tolist()
    res_string = ",".join(ticker_list)

    results_df = pd.DataFrame({
        "date": [date.today()],
        "tickers": [res_string],
    })

    return results_df


def diff_tickers(historical):
    added_tickers = {}
    removed_tickers = {}

    for i in range(1, len(historical.index)):
        prev_tickers = set(historical.iloc[i - 1].tickers)
        current_tickers = set(historical.iloc[i].tickers)

        added = current_tickers - prev_tickers
        if added:
            idx = historical.index[i]
            added_tickers[idx] = list(added)

        removed = prev_tickers - current_tickers
        if removed:
            idx = historical.index[i]
            removed_tickers[idx] = list(removed)

    at_only = pd.DataFrame(list(added_tickers.items()), columns=["date", "added_tickers"])
    rt_only = pd.DataFrame(list(removed_tickers.items()), columns=["date", "removed_tickers"])

    combined = pd.merge(at_only, rt_only, on=["date"], how="outer")
    combined = combined.sort_values("date", ascending=True)
    combined = combined.set_index("date")

    return combined


def main():
    hist_filename = "nikkei225_historical_components.csv"

    # Load or initialize historical tracker
    if os.path.exists(hist_filename):
        historical_df = pd.read_csv(hist_filename)
    else:
        historical_df = pd.DataFrame(columns=["date", "tickers"])

    # Fetch full Nikkei constituent data
    nikkei_df = load_nikkei_constituents()

    # Save FULL dataset (no columns dropped)
    nikkei_df.to_csv("nikkei225_constituents.csv", index=False)

    # Build ticker-only frame for tracking
    # Create a new DataFrame with 'ticker' column from 'Code'
    constituents = pd.DataFrame({
        "ticker": nikkei_df["Code"].tolist(),
        "date": date.today()
    })

    # Create historical row
    df = create_constituents(constituents)
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

    final = pd.concat([historical_df, df], ignore_index=True)
    final = final.drop_duplicates(subset=["date", "tickers"], keep="last")
    final.to_csv(hist_filename, index=False)

    # Diff logic
    historical = pd.read_csv(hist_filename, index_col="date")
    historical["tickers"] = historical["tickers"].apply(lambda x: sorted(x.split(",")))
    historical = historical.sort_index()

    combined = diff_tickers(historical)
    combined.to_csv("nikkei225_changes.csv")

    # README update
    if not combined.empty:
        changes_readme = combined.iloc[-50:].sort_index(ascending=False)
        markdown_table = changes_readme.to_markdown()
    else:
        markdown_table = "No historical variations recorded yet."

    readme_path = "README.md"
    if not os.path.exists(readme_path):
        with open(readme_path, "w", encoding="UTF-8") as f:
            f.write("\n" * 10)

    with open(readme_path, "r", encoding="UTF-8") as f:
        lines = f.readlines()

    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = lines[:10]
    lines += [f"Nikkei 225 Constituents Auto Renew at **{current_datetime}**"]
    lines += ["\n\n"]
    lines += [markdown_table]

    with open(readme_path, "w", encoding="UTF-8") as f:
        f.writelines(lines)


if __name__ == "__main__":
    main()