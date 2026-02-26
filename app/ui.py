import pandas as pd
from .constants import (
    STOCK_RED_MAX,
    STOCK_ORANGE_MIN,
    STOCK_ORANGE_MAX,
    STOCK_GREEN_MIN,
)

def stock_badge(qty: int) -> str:
    qty = int(qty)
    if qty <= STOCK_RED_MAX:
        return "🔴"
    if STOCK_ORANGE_MIN <= qty <= STOCK_ORANGE_MAX:
        return "🟠"
    if qty >= STOCK_GREEN_MIN:
        return "🟢"
    return "⚪️"

def format_stock_table(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["Level"] = df["on_hand"].apply(stock_badge)
    df["Availability"] = df["on_hand"].apply(lambda x: "Out of stock" if int(x) == 0 else "Available")

    df = df[["Level", "category", "item_name", "unit", "on_hand", "Availability"]]
    df = df.rename(
        columns={
            "category": "Category",
            "item_name": "Item",
            "unit": "Unit",
            "on_hand": "On hand",
        }
    )
    return df
