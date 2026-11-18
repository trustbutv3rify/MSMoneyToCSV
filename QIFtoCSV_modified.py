###############################################################################
###                                                                         ###
### Typical Use:  Takes the Loose exported QIF files from MS Money and      ###
###               converts them to CSV files for import into PowerBI        ###
###               Modified to allow function calls as well as standalone    ###
###               GUI                                                       ###
###                                                                         ###
###                                         trustbutv3rify - 2026/11/17     ###
###############################################################################
import os
import csv
import tkinter as tk
from tkinter import filedialog  # For GUI file selection

def convert_qif_to_csv(qif_file_path, csv_file_path):
    with open(qif_file_path, 'r') as qif_file, open(csv_file_path, 'w', newline='') as csv_file:
        qif_lines = qif_file.readlines()

        # Define headers for CSV, extended for investment transactions
        headers = ['Date', 'Amount', 'Payee', 'Memo', 'Category', 'Transaction Type', 'Security Name', 'Price', 'Quantity']
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(headers)

        i = 0
        while i < len(qif_lines):
            line = qif_lines[i].strip()
            
            if line.startswith('D'):
                # Initialize variables for each transaction
                date = amount = payee = memo = category = transaction_type = security_name = price = quantity = ''

                while i < len(qif_lines) and line.strip() != '^':  # Until the end of the transaction
                    field = line[0]  # The field indicator (D, T, N, etc.)
                    value = line[1:].strip()  # The value associated with the field

                    # Map fields to variables
                    if field == 'D':
                        date = value
                    elif field == 'T':
                        amount = value.replace(',', '')  # Remove commas from the amount
                    elif field == 'P':
                        payee = value
                    elif field == 'M':
                        memo = value
                    elif field == 'L':
                        category = value
                    elif field == 'N':
                        transaction_type = value
                    elif field == 'Y':
                        security_name = value
                    elif field == 'I':
                        price = value.replace(',', '')  # Remove commas from the price
                    elif field == 'Q':
                        quantity = value.replace(',', '')  # Remove commas from the quantity                
#                    elif field == 'E':
#                        memo_in_split = value
#                    elif field == 'S':
#                        category_in_split = value
#                    elif field == '$':
#                        split_amount = value	

                    i += 1
                    if i < len(qif_lines):
                        line = qif_lines[i].strip()
                
                # Adjust for "sell" transactions
                if transaction_type.lower() == 'sell':
                    if amount:
                        amount = f"-{abs(float(amount))}"  # Ensure negative value
                    if quantity:
                        quantity = f"-{abs(float(quantity))}"  # Ensure negative value

                
                # Write the transaction to CSV
                csv_writer.writerow([date, amount, payee, memo, category, transaction_type, security_name, price, quantity])

            i += 1

def main(qif_files=None, csv_dir=None):
    if qif_files is None:
        # Run GUI if no QIF files provided
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        
        # Allow multiple file selection
        qif_file_paths = filedialog.askopenfilenames(
            title="Select one or more QIF files to convert",
            filetypes=[("QIF files", "*.qif"), ("All files", "*.*")]
        )

        if not qif_file_paths:
            print("No files selected. Exiting.")
            return
        
        csv_dir = filedialog.askdirectory(
            title="Select output directory for CSV files"
        )

        if not csv_dir:
            print("No output directory selected. Exiting.")
            return

        # Assign qif_files to qif_file_paths
        qif_files = qif_file_paths
    
    else:
        # Use provided list of QIF files
        if csv_dir is None:
            raise ValueError("CSV directory must be provided when passing QIF files directly")

    os.makedirs(csv_dir, exist_ok=True)
    for qif_file in qif_files:
        csv_file_path = os.path.join(csv_dir, os.path.splitext(os.path.basename(qif_file))[0] + ".csv")
        try:
            convert_qif_to_csv(qif_file, csv_file_path)
            print(f"✅ Conversion complete: {os.path.basename(csv_file_path)}")
        except Exception as e:
            print(f"❌ Error converting {os.path.basename(qif_file)}: {e}")

    print("\nAll conversions complete.")

if __name__ == "__main__":
    main()