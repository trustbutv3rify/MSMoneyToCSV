#!/usr/bin/env python3
###############################################################################
###                                                                         ###
### Source:       Fork of the mny2qif.py file from the running-out-of-money ### 
###               repo by ThisNoName                                        ###
###                                                                         ###
### Typical Use:  Called from MNYtoCSV.py main program GUI entry to         ###
###               convert the MNY file to a series of QIF files from each   ###
###               Accounts in the MNY ledger                                ###
###                                                                         ###
###               Retained the CLI usage noted below for the devs that      ###
###               prefer the CLI.  Removed some CLI args.                   ###
###                                                                         ###
###                                          trustbutv3rify - 2026/11/18    ###
###############################################################################
"""
mny2qif_modified - export Microsoft Money (.mny) file to QIF.

Each exported account is written to its own QIF file, which is how Money's
own "loose QIF" export behaves.

Usage:
    python mny2qif_modified.py FILE.mny [-o OUTDIR]
"""

import argparse
import json
import os
import sys

from jet4 import JetDatabase
from money_modified import MoneyFile, ConversionError


def build_parser():
    p = argparse.ArgumentParser(
        prog="mny2qif",
        description="Export Microsoft Money (.mny) file to QIF.")
    p.add_argument("mny", metavar="FILE.mny", help="Microsoft Money file to read")
    p.add_argument("-o", "--out-dir", default=".",
                   help="directory to write the QIF files into (default: .)")
    #p.add_argument("--prefix",
    #               help="filename prefix for the QIF files "
    #                    "(default: the .mny file's base name)")
    #p.add_argument("-l", "--list", action="store_true",
    #               help="list the accounts and exit without writing anything")
    #p.add_argument("--include-closed", action="store_true", default=True,
    #               help="include closed accounts (default)")
    #p.add_argument("--skip-closed", dest="include_closed", action="store_false",
    #               help="omit accounts marked closed in Money")
    #p.add_argument("--no-manifest", dest="manifest", action="store_false",
    #               help="do not write the <prefix>_accounts.json sidecar that "
    #                    "tells qif2kmy which accounts are closed")
    return p


def main(mny_file, out_dir, prefix=None, include_closed=True, manifest=False):
    try:
        db = JetDatabase(mny_file)
        mny = MoneyFile(db)
    except (OSError, ValueError, ConversionError) as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 1

    for w in mny.warnings:
        sys.stderr.write("warning: %s\n" % w)

    accounts = mny.exportable_accounts()
    if not include_closed:
        accounts = [a for a in accounts if not a.closed]

    for a in mny.skipped_accounts():
        sys.stderr.write("skipping %r: %s accounts cannot be exported as QIF\n"
                         % (a.name, a.type_name))

    if not accounts:
        sys.stderr.write("error: no banking or credit card accounts to export\n")
        return 1

    # stem = prefix or os.path.splitext(os.path.basename(mny_file))[0] # If you want to add a filename prefix to the QIF files
    stem = None
    os.makedirs(out_dir, exist_ok=True)

    for a in accounts:
        path = os.path.join(out_dir, MoneyFile.filename_for(a, stem))
        # newline="" keeps the CRLF line endings that QIF files use.
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(mny.account_qif(a))
        print("%s  (%s, %d transactions%s)"
              % (path, a.type_name, len(a.transactions),
                 ", closed" if a.closed else ""))
    
    return 0

    if manifest:
        path = os.path.join(out_dir, MoneyFile.manifest_name(stem))
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(mny.manifest(stem, os.path.basename(mny_file)), fh,
                      indent=1)
            fh.write("\n")
        print("%s  (closed-account flags for qif2kmy)" % path)

def run():
    args = build_parser().parse_args()
    sys.exit(main(args.mny, args.out_dir, args.prefix, args.include_closed, args.manifest))

if __name__ == "__main__":
    run()