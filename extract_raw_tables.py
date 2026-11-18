###############################################################################
###                                                                         ###
### Typical Use:  Take the MNY file and extracts all the raw tables in the  ###
###               MNY Jet4 database to a 'raw_tables' sub-directory in the  ###
###               output directory.  Known tables are labeled, unmapped     ###
###               tables are in the 'raw_tables\other_tables' sub-directory.###
###                                                                         ###
###               Modified to allow function calls as well as standalone    ###
###               GUI.                                                      ###
###                                                                         ###
###   CLI Usage: python extract_raw_tables.py [File.mny] [OUTPUT DIR]       ###
###                                                                         ###
###                                         trustbutv3rify - 2026/11/18     ###
###############################################################################
import os
import sys
import pandas as pd
from jet4 import JetDatabase
from money_modified import MoneyFile, INV_ACTIONS


def extract_raw_tables(mny_file_path, output_dir):
    db = JetDatabase(mny_file_path)
    money = MoneyFile(db)

    raw_tables_dir = os.path.join(output_dir, "raw_tables")
    os.makedirs(raw_tables_dir, exist_ok=True)

    exported_tdef_pages = set()

    # 1. Accounts.csv
    acct_table = db.find_table(["hacct", "szFull", "at"])
    if acct_table:
        exported_tdef_pages.add(acct_table.tdef_page)

    account_rows = []
    for account in sorted(money.accounts.values(), key=lambda a: a.hacct):
        account_rows.append({
            "AccountID": str(account.hacct),
            "AccountName": account.name,
            "AccountTypeCode": account.at,
            "AccountType": account.type_name,
            "OpeningBalance": account.open_balance,
            "OpeningDate": account.dt_open,
            "ClosingDate": account.dt_close,
            "IsClosed": account.closed,
            "Institution": account.institution,
            "TransactionCount": len(account.transactions),
        })
    pd.DataFrame(account_rows).to_csv(
        os.path.join(raw_tables_dir, "Accounts.csv"), index=False
    )

    # 2. Categories.csv
    cat_table = db.find_table(["hcat", "szFull", "hcatParent"])
    if cat_table:
        exported_tdef_pages.add(cat_table.tdef_page)

    category_rows = []
    for hcat, cat in getattr(money, "_cat_rows", {}).items():
        parent_id = cat.get("hcatParent") if isinstance(cat, dict) else getattr(cat, "hcatParent", None)
        is_income = cat.get("bIncome", False) if isinstance(cat, dict) else getattr(cat, "bIncome", False)
        category_rows.append({
            "CategoryID": str(hcat),
            "CategoryPath": money.category_path(hcat),
            "ParentCategoryID": str(parent_id) if parent_id not in (None, -1) else "",
            "IsIncome": bool(is_income),
        })
    pd.DataFrame(category_rows).to_csv(
        os.path.join(raw_tables_dir, "Categories.csv"), index=False
    )

    # 3. Payees.csv
    payee_rows = []
    payee_table = db.find_table(["hpay", "szFull"], forbidden=["htrn", "hacct"])
    if payee_table:
        exported_tdef_pages.add(payee_table.tdef_page)
        for row in payee_table.rows():
            if row.get("hpay") is not None:
                payee_rows.append({
                    "PayeeID": str(row.get("hpay")),
                    "PayeeName": row.get("szFull", ""),
                })
    pd.DataFrame(payee_rows).to_csv(
        os.path.join(raw_tables_dir, "Payees.csv"), index=False
    )

    # 4. Securities.csv
    sec_rows = []
    sec_table = db.find_table(["hsec", "szFull"], forbidden=["htrn", "hacct", "dt"])
    if sec_table:
        exported_tdef_pages.add(sec_table.tdef_page)
        for row in sec_table.rows():
            if row.get("hsec") is not None:
                sec_rows.append({
                    "SecurityID": str(row.get("hsec")),
                    "Symbol": row.get("szSymbol") or row.get("szTick") or "",
                    "SecurityName": row.get("szFull") or "",
                    "Exchange": row.get("szExchg") or "",
                    "SecurityType": row.get("sect", ""),
                    "CUSIP": row.get("szCusip") or "",
                })
    pd.DataFrame(sec_rows).to_csv(
        os.path.join(raw_tables_dir, "Securities.csv"), index=False
    )

    # 5. InvestmentTransactions.csv (Share Price, Quantity, Commission)
    inv_rows = []
    inv_by_htrn = {}
    inv_table = db.find_table(["htrn", "dPrice", "qty"])
    if inv_table:
        exported_tdef_pages.add(inv_table.tdef_page)
        for row in inv_table.rows():
            htrn = row.get("htrn")
            if htrn is not None:
                inv_by_htrn[htrn] = row
                inv_rows.append({
                    "TransactionID": str(htrn),
                    "Price": row.get("dPrice"),
                    "Quantity": row.get("qty"),
                    "Commission": row.get("amtCmn"),
                    "CommissionUser": row.get("amtCmnUser"),
                    "AccruedInterest": row.get("amtInt"),
                    "LotID": str(row.get("lott")) if row.get("lott") not in (None, -1) else "",
                })
    pd.DataFrame(inv_rows).to_csv(
        os.path.join(raw_tables_dir, "InvestmentTransactions.csv"), index=False
    )

    # 6. SecurityPrices.csv (Historical Market Quotes)
    price_rows = []
    price_table = db.find_table(["hsp", "dt", "hsec", "dPrice"])
    if price_table:
        exported_tdef_pages.add(price_table.tdef_page)
        for row in price_table.rows():
            if row.get("hsec") is not None:
                price_rows.append({
                    "PriceID": str(row.get("hsp")),
                    "SecurityID": str(row.get("hsec")),
                    "Date": row.get("dt"),
                    "Price": row.get("dPrice"),
                    "Open": row.get("dOpen"),
                    "High": row.get("dHigh"),
                    "Low": row.get("dLow"),
                    "Volume": row.get("vol"),
                    "Source": row.get("src"),
                })
    pd.DataFrame(price_rows).to_csv(
        os.path.join(raw_tables_dir, "SecurityPrices.csv"), index=False
    )

    # 7. SecurityLots.csv (Tax Lots / Cost Basis)
    lot_rows = []
    lot_table = db.find_table(["hlot", "htrnBuy", "qty", "hsec"])
    if lot_table:
        exported_tdef_pages.add(lot_table.tdef_page)
        for row in lot_table.rows():
            if row.get("hlot") is not None:
                lot_rows.append({
                    "LotID": str(row.get("hlot")),
                    "AccountID": str(row.get("hacct")) if row.get("hacct") is not None else "",
                    "SecurityID": str(row.get("hsec")) if row.get("hsec") is not None else "",
                    "BuyTransactionID": str(row.get("htrnBuy")) if row.get("htrnBuy") is not None else "",
                    "SellTransactionID": str(row.get("htrnSell")) if row.get("htrnSell") is not None else "",
                    "BuyDate": row.get("dtBuy"),
                    "SellDate": row.get("dtSell"),
                    "Quantity": row.get("qty"),
                })
    pd.DataFrame(lot_rows).to_csv(
        os.path.join(raw_tables_dir, "SecurityLots.csv"), index=False
    )

    # 8. Transactions.csv
    transaction_rows = []
    trn_by_id = {}
    trn_table = db.find_table(["htrn", "hacct", "dt", "amt"])
    if trn_table:
        exported_tdef_pages.add(trn_table.tdef_page)
        for row in trn_table.rows():
            htrn = row.get("htrn")
            if htrn is None:
                continue
            trn_by_id[htrn] = row

            flags = row.get("grftt", 0) or 0
            is_template = bool(flags & 0x200000)
            is_split_child = bool(flags & 0x40)
            raw_payee = row.get("hpay") if row.get("hpay") is not None else row.get("lHpay")
            native_act = row.get("act")
            inv_detail = inv_by_htrn.get(htrn, {})

            transaction_rows.append({
                "TransactionID": str(htrn),
                "AccountID": str(row.get("hacct")) if row.get("hacct") is not None else "",
                "Date": row.get("dt"),
                "Amount": row.get("amt"),
                "CategoryID": str(row.get("hcat")) if row.get("hcat") not in (None, -1) else "",
                "PayeeID": str(raw_payee) if raw_payee not in (None, -1) else "",
                "SecurityID": str(row.get("hsec")) if row.get("hsec") not in (None, -1) else "",
                "NativeInvestmentAction": str(native_act) if native_act not in (None, -1) else "",
                "InvestmentAction": INV_ACTIONS.get(native_act, ""),
                "SharePrice": inv_detail.get("dPrice", ""),
                "ShareQuantity": inv_detail.get("qty", ""),
                "Commission": inv_detail.get("amtCmn", ""),
                "Memo": row.get("mMemo") or "",
                "Number": row.get("szId") or "",
                "ClearedStatus": row.get("cs"),
                "TransactionFlags": flags,
                "IsScheduledTemplate": is_template,
                "IsSplitChild": is_split_child,
                "TransferAccountID": str(row.get("hacctLink")) if row.get("hacctLink") not in (None, -1) else "",
            })
    pd.DataFrame(transaction_rows).to_csv(
        os.path.join(raw_tables_dir, "Transactions.csv"), index=False
    )

    # 9. Splits.csv
    split_rows = []
    split_table = db.find_table(["htrn", "htrnParent", "iSplit"])
    if split_table:
        exported_tdef_pages.add(split_table.tdef_page)
        for row in split_table.rows():
            child_id = row.get("htrn")
            child_trn = trn_by_id.get(child_id, {})
            hcat = child_trn.get("hcat")
            hacct_link = child_trn.get("hacctLink")

            split_rows.append({
                "TransactionID": str(child_id),
                "ParentTransactionID": str(row.get("htrnParent")),
                "SplitIndex": row.get("iSplit") or 0,
                "Amount": child_trn.get("amt"),
                "CategoryID": str(hcat) if hcat not in (None, -1) else "",
                "TransferAccountID": str(hacct_link) if hacct_link not in (None, -1) else "",
                "Memo": child_trn.get("mMemo") or "",
            })
    pd.DataFrame(split_rows).to_csv(
        os.path.join(raw_tables_dir, "Splits.csv"), index=False
    )

    # 10. Dump EVERY remaining unmapped table in the .MNY database to raw_tables/other_tables/
    other_dir = os.path.join(raw_tables_dir, "other_tables")
    os.makedirs(other_dir, exist_ok=True)
    for idx, tbl in enumerate(db.tables):
        if tbl.tdef_page in exported_tdef_pages or tbl.num_rows == 0:
            continue
        rows = list(tbl.rows())
        if not rows:
            continue
        first_col = tbl.colnames if tbl.colnames else "unknown"
        safe_col = "".join(c if c.isalnum() else "_" for c in first_col)[:20]
        fname = f"Table_{idx:02d}_{safe_col}.csv"
        pd.DataFrame(rows).to_csv(os.path.join(other_dir, fname), index=False)

    # Use os.path.join to ensure the path is correctly formatted
    formatted_path = os.path.join(output_dir, "raw_tables")
    # Replace backslashes with forward slashes for consistent display
    # Normalize the path to ensure consistent backslashes in the console
    formatted_path = os.path.normpath(formatted_path)
    print(f"Raw tables extracted and saved to {formatted_path}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python extract_raw_tables.py <mny_file_path> <output_dir>")
        sys.exit(1)
    mny_file_path = sys.argv[1]
    output_dir = sys.argv[2]
    extract_raw_tables(mny_file_path, output_dir)