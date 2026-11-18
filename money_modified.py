###############################################################################
###                                                                         ###
### Source:       Fork of the money.py file from the running-out-of-money   ### 
###               repo by ThisNoName.                                       ###
###               Modified to include and parse more account types          ###
###                                                                         ###
### Typical Use:  Called from the mny2qif_modified.py to enumerate the      ###
###               Accounts in the MNY ledger.                               ###
###                                                                         ###
###                                          trustbutv3rify - 2026/11/18    ###
###############################################################################
"""
Microsoft Money (.mny) -> QIF conversion for Accounts in the ledger.

Money's system catalogue is encrypted, so the tables below are located by
their column signature rather than by name (see jet4.JetDatabase.find_table).

"""

import datetime

# ACCT.at values.  Only the two types below can be represented in QIF by this
# tool; everything else (investment, loan, asset, ...) is reported and skipped.

AT_BANK = 0
AT_CREDIT_CARD = 1
AT_CASH = 2
AT_ASSET = 3
AT_LIABILITY = 4
AT_INVESTMENT = 5
AT_LOAN = 6
AT_LOC = 7
AT_MORTGAGE = 8

QIF_TYPE = {
    AT_BANK: "!Type:Bank",
    AT_CREDIT_CARD: "!Type:CCard",
    AT_CASH: "!Type:Cash",
    AT_ASSET: "!Type:Oth A",
    AT_LIABILITY: "!Type:Oth L",
    AT_INVESTMENT: "!Type:Invst",
    AT_LOAN: "!Type:Oth L",
    AT_LOC: "!Type:Oth L",
    AT_MORTGAGE: "!Type:Oth L",
}

INV_ACTIONS = {
    1: "Buy",
    2: "Sell",
    3: "Div",
    4: "Int",
    8: "RtrnCap",
    9: "ReinvDiv",
    10: "ReinvInt",
    12: "ShrsIn",
    13: "ShrsOut",
    24: "CGShort",
    26: "CGLong",
    27: "ReinvSh",
    29: "ReinvLg",
    32: "ShrsIn",
    33: "ShrsOut",
}

AT_NAMES = {
    0: "bank",
    1: "credit card",
    2: "cash",
    3: "asset",
    4: "liability",
    5: "investment",
    6: "loan",
    7: "line of credit",
    8: "mortgage",
    9: "employee stock option",
    10: "other",
}

# TRN.grftt bit marking a scheduled/recurring bill template rather than a real
# register entry.  Money does not export these.
TT_SCHEDULED = 0x00200000

# TRN.cs (cleared state) -> QIF C value.
CLEARED_FLAG = {1: "*", 2: "X"}

CRLF = "\r\n"

# Written next to the QIF files, holding what QIF cannot express.  qif2kmy
# looks for this suffix in the directories it is given.
MANIFEST_SUFFIX = "_accounts.json"


class ConversionError(Exception):
    pass


def _fmt_date(d):
    """Money writes QIF dates as M/D'YYYY (no zero padding)."""
    #return "%d/%d'%04d" % (d.month, d.day, d.year)
    """Custom:  Money QIF dates as YYYY-MM-DD (with zero padding)."""
    return "%04d-%02d-%02d" % (d.year, d.month, d.day)


def _fmt_amount(a):
    return "{:,.2f}".format(a or 0.0)

def _fmt_precise(a):
    """Format share price / quantity cleanly without trailing zeroes."""
    s = "{:.6f}".format(a or 0.0).rstrip("0").rstrip(".")
    return s if s else "0"

def _sanitize(name):
    out = "".join(c if (c.isalnum() or c in " -_") else "_" for c in name)
    return "_".join(out.split()) or "account"

def _qif_text(s):
    """Match MS Money's ANSI QIF exporter by stripping non-ASCII symbols like ®."""
    if not s:
        return s
    return s.replace("\u00ae", " ").replace("\u2122", " ").encode("ascii", "ignore").decode("ascii")


class Account:
    def __init__(self, row):
        self.row = row
        self.hacct = row["hacct"]
        self.name = row["szFull"] or "Account %s" % self.hacct
        self.at = row["at"]
        self.open_balance = row.get("amtOpen") or 0.0
        self.dt_open = row.get("dtOpen")
        self.dt_close = row.get("dtClose")
        self.institution = None
        self.transactions = []

    @property
    def closed(self):
        """Money sets ACCT.fClosed when an account is closed, and stamps
        ACCT.dtClose with the date.  Either one on its own still means closed.
        """
        return bool(self.row.get("fClosed")) or self.dt_close is not None

    @property
    def exportable(self):
        return self.at in QIF_TYPE

    @property
    def type_name(self):
        return AT_NAMES.get(self.at, "type %s" % self.at)

    @property
    def opening_date(self):
        """The date Money stamps on the synthetic opening-balance record.

        It is the earliest date the account has any history for: the account's
        own open date if set, otherwise (and if earlier) its first transaction.
        """
        candidates = [t.date for t in self.transactions if t.date]
        if self.dt_open:
            candidates.append(self.dt_open)
        return min(candidates) if candidates else datetime.datetime.now()


class Transaction:
    def __init__(self, row):
        self.htrn = row["htrn"]
        self.hacct = row["hacct"]
        self.hacct_link = row.get("hacctLink")
        self.date = row.get("dt")
        self.amount = row.get("amt") or 0.0
        self.hcat = row.get("hcat")
        self.hpay = row.get("lHpay")
        self.hsec = row.get("hsec")
        self.act = row.get("act")
        self.cleared = row.get("cs") or 0
        self.grftt = row.get("grftt") or 0
        self.memo = row.get("mMemo")
        self.number = row.get("szId")
        self.splits = []

    @property
    def scheduled(self):
        return bool(self.grftt & TT_SCHEDULED)


class Split:
    def __init__(self, row):
        self.htrn = row["htrn"]
        self.parent = row["htrnParent"]
        self.index = row.get("iSplit") or 0
        self.category = None
        self.memo = None
        self.amount = 0.0


class MoneyFile:
    """Reads the Money tables needed for a QIF export."""

    def __init__(self, db):
        self.db = db
        self.accounts = {}
        self.categories = {}
        self.payees = {}
        self.warnings = []
        self.securities = {} 
        self.inv_txns = {}
        self._load()

    # -- loading ---------------------------------------------------------

    def _table(self, label, required, forbidden=(), optional=False):
        t = self.db.find_table(required, forbidden)
        if t is None and not optional:
            raise ConversionError(
                "could not locate the %s table (no table has columns %s); "
                "this may not be a Microsoft Money file"
                % (label, ", ".join(required)))
        return t

    def _read_all(self, table, label):
        """Read a whole table, recording anything that looks like data loss."""
        rows = list(table.rows())
        if table.read_errors:
            self.warnings.append("%s: %d row(s) could not be decoded"
                                 % (label, table.read_errors))
        if len(rows) < table.num_rows:
            self.warnings.append("%s: read %d of %d row(s) recorded in the file"
                                 % (label, len(rows), table.num_rows))
        return rows

    def _load(self):
        acct_t = self._table("account (ACCT)", ["hacct", "szFull", "at"])
        trn_t = self._table("transaction (TRN)",
                            ["htrn", "hacct", "dt", "amt", "hcat", "cs", "grftt"])
        cat_t = self._table("category (CAT)", ["hcat", "szFull", "hcatParent"])
        pay_t = self._table("payee (PAY)", ["hpay", "szFull", "hpayParent"],
                            optional=True)
        split_t = self._table("split (TRN_SPLIT)", ["htrn", "htrnParent", "iSplit"],
                              optional=True)
        bill_t = self._table("recurring bill (BILL)",
                             ["hbill", "frq", "iinstNextUnpaid"], optional=True)

        institutions = {}
        fi_t = self._table("institution (FI)", ["hfi", "szFull", "haddr", "fHidden"],
                           optional=True)
        if fi_t:
            institutions = {r["hfi"]: r["szFull"]
                            for r in self._read_all(fi_t, "institutions")
                            if r["hfi"] is not None and r["szFull"]}

        for r in self._read_all(acct_t, "accounts"):
            if r["hacct"] is not None:
                acct = Account(r)
                acct.institution = institutions.get(r.get("hfi"))
                self.accounts[r["hacct"]] = acct

        self._cat_rows = {r["hcat"]: r
                          for r in self._read_all(cat_t, "categories")
                          if r["hcat"] is not None}
        if pay_t:
            self.payees = {r["hpay"]: r["szFull"]
                           for r in self._read_all(pay_t, "payees")
                           if r["hpay"] is not None}

        # Transactions referenced by a scheduled bill are templates, not
        # register entries.  Money excludes them and so do we.
        scheduled = set()
        if bill_t:
            for r in bill_t.rows():
                if r.get("lHtrn") not in (None, -1):
                    scheduled.add(r["lHtrn"])
        xfer_t = self._table("transfer (TRN_XFER)", ["htrnFrom", "htrnLink"],
                             optional=True)
        if xfer_t and scheduled:
            for r in xfer_t.rows():
                a, b = r.get("htrnFrom"), r.get("htrnLink")
                if a in scheduled or b in scheduled:
                    scheduled.update(x for x in (a, b) if x is not None)

        self.transactions = {}
        for r in self._read_all(trn_t, "transactions"):
            if r["htrn"] is None:
                continue
            t = Transaction(r)
            # A row with no account cannot appear in any register.
            if t.hacct is None or t.scheduled or t.htrn in scheduled:
                continue
            ### 1. ps == 1 (not ps == 2 or ps == 4!) - skips voided/skipped recurring bill instances (ps=1, ps=3, ps=4) 
            ### 2. grfstem == 2051 (0x0803 — template/skipped bill instance flag; normal rows have grfstem == 0!)
            ### 3. hbillHead is not None (57 — attached to a recurring bill series as an unposted/skipped instance)
            #if (t.hacct is None or t.scheduled or t.htrn in scheduled
            #        or r.get("ps") == 1 or (r.get("grfstem") or 0) != 0):
            #    continue
            #if (t.hacct is None or t.scheduled or t.htrn in scheduled
            #        or r.get("hbillHead") is not None):
            #    continue
            self.transactions[t.htrn] = t

        if split_t:
            self._attach_splits(split_t)

        for t in self.transactions.values():
            acct = self.accounts.get(t.hacct)
            if acct is not None:
                acct.transactions.append(t)
        for acct in self.accounts.values():
            acct.transactions.sort(key=lambda t: (t.date or datetime.datetime.min,
                                                  t.htrn))

        sec_t = self._table("security (SEC)", ["hsec", "szFull"], optional=True)
        if sec_t:
            self.securities = {
                r["hsec"]: {"name": r["szFull"], "symbol": r.get("szSymbol")}
                for r in self._read_all(sec_t, "securities")
                if r["hsec"] is not None
            }

        inv_t = self._table("investment txn (TRN_INV)", ["htrn", "dPrice", "qty"],
                            optional=True)
        if inv_t:
            self.inv_txns = {
                r["htrn"]: r
                for r in self._read_all(inv_t, "investment transactions")
                if r["htrn"] is not None
            }

    def _attach_splits(self, split_t):
        for r in split_t.rows():
            parent = self.transactions.get(r.get("htrnParent"))
            child = self.transactions.pop(r.get("htrn"), None)
            if parent is None or child is None:
                continue
            s = Split(r)
            s.amount = child.amount
            s.memo = child.memo
            s.category = self.transfer_or_category(child)
            parent.splits.append(s)
        for t in self.transactions.values():
            t.splits.sort(key=lambda s: s.index)

    # -- lookups ---------------------------------------------------------

    def category_path(self, hcat):
        """Full 'Parent:Child' category name, excluding the INCOME/EXPENSE root."""
        if hcat in (None, -1):
            return None
        if hcat in self.categories:
            return self.categories[hcat]
        parts = []
        seen = set()
        cur = hcat
        while cur not in (None, -1) and cur not in seen:
            seen.add(cur)
            row = self._cat_rows.get(cur)
            if row is None:
                break
            parts.append(row["szFull"] or "")
            cur = row.get("hcatParent")
        #if len(parts) > 1:
        if parts:
            parts.pop()  # drop the top-level INCOME / EXPENSE root
        path = ":".join(reversed([p for p in parts if p]))
        self.categories[hcat] = path or None
        return self.categories[hcat]

    def payee_name(self, hpay):
        if hpay in (None, -1):
            return None
        return self.payees.get(hpay)

    def transfer_or_category(self, t):
        """QIF 'L' value: a bracketed account for transfers, else the category."""
        if t.hacct_link not in (None, -1):
            other = self.accounts.get(t.hacct_link)
            if other is not None:
                return "[%s]" % other.name
        return self.category_path(t.hcat)

    # -- QIF output ------------------------------------------------------

    def _investment_lines(self, t):
        """Format a single investment transaction (!Type:Invst) into QIF lines."""
        lines = ["D" + _fmt_date(t.date) if t.date else "D"]
        flag = CLEARED_FLAG.get(t.cleared)
        if flag:
            lines.append("C" + flag)
        if t.memo:
            lines.append("M" + t.memo)
        lines.append("T" + _fmt_amount(abs(t.amount)))

        inv_row = self.inv_txns.get(t.htrn)
        sec = self.securities.get(t.hsec, {}) if t.hsec not in (None, -1) else {}

        if inv_row or sec or (t.act not in (None, -1)):
            action = INV_ACTIONS.get(t.act, "MiscINCOME" if t.amount >= 0 else "MiscEXPENSE")
            lines.append("N" + action)
            if sec.get("name"):
                lines.append("Y" + _qif_text(sec["name"])) #sanitize QIF string
            if inv_row:
                price = inv_row.get("dPrice")
                shares = inv_row.get("qty")
                commission = inv_row.get("amtCmn")
                if price:
                    lines.append("I" + _fmt_precise(price))
                elif action in ("ShrsIn", "ShrsOut"):
                    lines.append("I")
                if shares:
                    lines.append("Q" + _fmt_precise(abs(shares)))
                if commission:
                    lines.append("O" + _fmt_amount(abs(commission)))
        else:
            lines.append("N" + ("MiscINCOME" if t.amount >= 0 else "MiscEXPENSE"))

        cat = self.category_path(t.hcat)
        if cat:
            lines.append("L" + cat)

        lines.append("^")
        return lines

        sec = self.securities.get(inv_row.get("hsec"), {})
        action = INV_ACTIONS.get(inv_row.get("itt"), "MiscExp")
        shares = inv_row.get("dShares") or 0.0
        price = inv_row.get("dPrice") or 0.0
        commission = inv_row.get("amtComm") or 0.0
        dest = self.transfer_or_category(t)
        if dest:
            lines.append("L" + dest)
        if t.memo:
            lines.append("M" + t.memo)


    def account_qif(self, acct):
        """Render one account as a complete QIF document."""
        lines = [QIF_TYPE[acct.at]]

        # Money leads with a synthetic opening-balance record, modelled as a
        # reconciled transfer from the account to itself.
        #if acct.open_balance != 0.0:
        if acct.at != AT_INVESTMENT :
            lines += ["D" + _fmt_date(acct.opening_date),
                    "T" + _fmt_amount(acct.open_balance),
                    "CX",
                    "POpening Balance",
                    "L[%s]" % acct.name,
                    "^"]

        for t in acct.transactions:
            if acct.at == AT_INVESTMENT:
                    lines.extend(self._investment_lines(t))
                    continue
            lines.append("D" + _fmt_date(t.date) if t.date else "D")
            if t.amount != 0.0:
                lines.append("T" + _fmt_amount(t.amount))
            flag = CLEARED_FLAG.get(t.cleared)
            if flag:
                lines.append("C" + flag)
            if t.number:
                lines.append("N" + t.number)
            payee = self.payee_name(t.hpay)
            if payee:
                lines.append("P" + payee)
            if t.memo:
                lines.append("M" + t.memo)

            dest = self.transfer_or_category(t)
            if dest:
                lines.append("L" + dest)

            if t.splits:
                for s in t.splits:
                    lines.append("S" + (s.category or ""))
                    if s.memo:
                        lines.append("E" + s.memo)
                    lines.append("$" + _fmt_amount(s.amount))

            lines.append("^")

        return CRLF.join(lines) + CRLF

    def exportable_accounts(self):
        return [a for a in sorted(self.accounts.values(), key=lambda a: a.hacct)
                if a.exportable]

    def skipped_accounts(self):
        return [a for a in sorted(self.accounts.values(), key=lambda a: a.hacct)
                if not a.exportable]

    @staticmethod
    def filename_for(acct, stem):
        # return "%s_%s.qif" % (stem, _sanitize(acct.name))
        return "%s.qif" % (_sanitize(acct.name))
    
    @staticmethod
    def manifest_name(stem):
        return stem + MANIFEST_SUFFIX

    def manifest(self, stem, source):
        """The account facts QIF has no field for, for qif2kmy to pick up.

        QIF describes a register, not an account, so there is nowhere to say
        that Money had an account closed.  Writing it alongside the QIF files
        keeps them byte-for-byte what Money itself would have exported.

        Every exportable account is listed, including ones --skip-closed left
        out, so that an omitted account still reached by a transfer can be
        marked closed rather than quietly reopened.
        """
        return {
            "generator": "mny2qif",
            "source": source,
            "accounts": [
                {
                    "name": a.name,
                    "qif": self.filename_for(a, stem),
                    "closed": a.closed,
                    "institution": a.institution,
                }
                for a in self.exportable_accounts()
            ],
        }
