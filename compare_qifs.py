###################################################################################
###                                                                             ###
### Typical Use: Troubleshooting / Debug tool to compare QIF files              ###
###                                                                             ###
###              Transaction by transaction comparison between two QIFs.        ###
###              Was used to compare direct QIF export from MS Money            ###
###              against the mny2qif_modified.py to ensure all transactions     ###
###              were exported.                                                 ###
###                                                                             ###
###     Output: Three TXT files                                                 ###
###             1) Transactions only in File1                                   ###
###             2) Transactions only in File2                                   ###
###             3) Transactions in both files                                   ###
###                                                                             ###
###   CLI Usage: python compare_qifs.py [File1.qif] [File2.qif] -o [Output Dir] ###
###                                                                             ###
###     Options: --strict                                                       ###        
###              Compares more than just date and amount transaction fields     ###
###                                                                             ###
###                                     trustbutv3rify - 2026/11/18             ###
###################################################################################

import argparse
import re
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

### Example usage: C:\>python compare_qif.py ms_money_export.qif mny2qif_output.qif -o ./diff_results --strict ###
"""If --strict flags any mismatches on your investment accounts, it will almost certainly be an INV_ACTIONS code 
(e.g., MS Money exporting BuyX vs Buy or DivX vs Div when transferring cash from a linked brokerage cash account) 
or a security name formatting detail—both of which show up side-by-side in only_in_file1.txt and only_in_file2.txt."""

def normalize_date(raw_date: str) -> str:
    """Converts M/D'YYYY, M/D/YYYY, or YYYY-MM-DD into YYYY-MM-DD."""
    s = raw_date.strip().replace("'", "/")
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    parts = s.split("/")
    if len(parts) == 3:
        m, d, y = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if len(y) == 2:
            y = ("19" if int(y) >= 70 else "20") + y
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    return s


def normalize_decimal(raw_val: str | None, places: str = "0.01") -> Decimal:
    """Strips commas/whitespace and normalizes to fixed decimal precision."""
    if not raw_val:
        return Decimal(places) * 0
    cleaned = raw_val.strip().replace(",", "")
    try:
        return Decimal(cleaned).quantize(Decimal(places))
    except InvalidOperation:
        return Decimal(places) * 0

def _qif_text(s: str) -> str:
    """Normalize non-ASCII symbols like ® and collapse double spaces for comparison."""
    if not s:
        return s
    cleaned = s.replace("\u00ae", " ").replace("\u2122", " ").encode("ascii", "ignore").decode("ascii")
    return " ".join(cleaned.split())

def parse_qif(filepath: Path, strict: bool = False) -> list[dict]:
    """Parses a QIF file into transaction dicts with standard or strict comparison keys."""
    transactions = []
    current_lines = []
    qif_type = ""

    fields = {}
    splits = []
    cur_split_cat = ""

    def finalize_record():
        if not current_lines:
            return
        norm_date = normalize_date(fields.get("D", "")) if fields.get("D") else "UNKNOWN-DATE"
        norm_amt = normalize_decimal(fields.get("T"), "0.01")

        if not strict:
            key = (norm_date, norm_amt)
        elif "invst" in qif_type.lower():
            action = fields.get("N", "").strip().lower()
            security = _qif_text(fields.get("Y", "").strip().lower())
            shares = normalize_decimal(fields.get("Q"), "0.0001")
            price = normalize_decimal(fields.get("I"), "0.0001")
            comm = normalize_decimal(fields.get("O"), "0.01")
            key = (norm_date, norm_amt, action, security, shares, price, comm)
        else:
            payee = fields.get("P", "").strip().lower()
            category = fields.get("L", "").strip().lower()
            norm_splits = tuple(sorted((c.strip().lower(), normalize_decimal(a, "0.01")) for c, a in splits))
            key = (norm_date, norm_amt, payee, category, norm_splits)

        transactions.append({
            "key": key,
            "date": norm_date,
            "amount": norm_amt,
            "raw": "\n".join(current_lines) + "\n^",
        })

    with filepath.open("r", encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if not line:
                continue

            if line.startswith("!"):
                qif_type = line.strip()
                continue

            if line == "^":
                finalize_record()
                current_lines = []
                fields = {}
                splits = []
                cur_split_cat = ""
                continue

            current_lines.append(line)
            code, val = line[0], line[1:]

            if code == "S":
                cur_split_cat = val
            elif code == "$":
                splits.append((cur_split_cat, val))
                cur_split_cat = ""
            elif code not in fields:
                fields[code] = val

    return transactions


def write_report(out_path: Path, title: str, records: list[dict]) -> None:
    """Writes matched or unmatched transaction records to a text file."""
    with out_path.open("w", encoding="utf-8") as out:
        out.write(f"{title} (Total: {len(records)})\n")
        out.write("=" * 60 + "\n\n")
        for idx, rec in enumerate(records, start=1):
            out.write(f"[{idx}] Date: {rec['date']} | Net Amount: {rec['amount']}\n")
            out.write(rec["raw"] + "\n\n")


def compare_qif_files(file1: Path, file2: Path, out_dir: Path, strict: bool = False) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    txns1 = parse_qif(file1, strict=strict)
    txns2 = parse_qif(file2, strict=strict)

    buckets1 = defaultdict(list)
    for t in txns1:
        buckets1[t["key"]].append(t)

    buckets2 = defaultdict(list)
    for t in txns2:
        buckets2[t["key"]].append(t)

    counts1 = Counter(t["key"] for t in txns1)
    counts2 = Counter(t["key"] for t in txns2)

    only_in_1 = []
    only_in_2 = []
    in_both = []

    all_keys = sorted(set(counts1.keys()) | set(counts2.keys()), key=str)

    for key in all_keys:
        c1 = counts1[key]
        c2 = counts2[key]
        matched = min(c1, c2)

        for i in range(matched):
            in_both.append({
                "date": key[0],
                "amount": key[1],
                "raw": f"--- FILE 1 ---\n{buckets1[key][i]['raw']}\n--- FILE 2 ---\n{buckets2[key][i]['raw']}",
            })

        for i in range(matched, c1):
            only_in_1.append(buckets1[key][i])

        for i in range(matched, c2):
            only_in_2.append(buckets2[key][i])

    out1 = out_dir / "only_in_file1.txt"
    out2 = out_dir / "only_in_file2.txt"
    out_both = out_dir / "in_both_files.txt"

    mode_label = "STRICT" if strict else "STANDARD (Date + Amount)"
    write_report(out1, f"[{mode_label}] Transactions ONLY in {file1.name}", only_in_1)
    write_report(out2, f"[{mode_label}] Transactions ONLY in {file2.name}", only_in_2)
    write_report(out_both, f"[{mode_label}] Transactions in BOTH {file1.name} and {file2.name}", in_both)

    print(f"Comparison complete ({mode_label}):")
    print(f"  Only in File 1 ({file1.name}): {len(only_in_1)} -> {out1}")
    print(f"  Only in File 2 ({file2.name}): {len(only_in_2)} -> {out2}")
    print(f"  In Both Files:                 {len(in_both)} -> {out_both}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare two QIF files.")
    parser.add_argument("file1", type=Path, help="Path to file1 (MS Money QIF)")
    parser.add_argument("file2", type=Path, help="Path to file2 (mny2qif output QIF)")
    parser.add_argument("-o", "--out-dir", type=Path, default=Path("."), help="Output directory for TXT reports")
    parser.add_argument("--strict", action="store_true", help="Also compare Action, Security, Shares, Price, Payee, Category, and Splits")
    args = parser.parse_args()

    compare_qif_files(args.file1, args.file2, args.out_dir, strict=args.strict)