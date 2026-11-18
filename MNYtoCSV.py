###############################################################################
###                                                                         ###
### Typical Use:  Main program entry point for the MNY to CSV converter.    ###
###                                                                         ###
###               GUI is called, config is created (MNY_Config.txt) to      ###
###               hold the input to the MNY file and output direction, then ###
###               runs, in order:                                           ###
###               1) the mny2qif_modified.py to convert MNY to QIF files    ###
###               2) QIFtoCSV_modified.py to convert the QIF files to CSVs  ###
###               3) Optional: export_raw_tables.py to debug/troubleshoot   ### 
###                 the MNY parsing from the raw table exports              ###
###                                                                         ###
###               Retained the CLI usage for each individual file if full   ###
###               workflow is not desired                                   ###
###                                                                         ###
###                                      trustbutv3ify - 2026/11/18         ###
###############################################################################

import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
from mny2qif_modified import main as mny2qif_main
from QIFtoCSV_modified import main as qif_to_csv_main
from extract_raw_tables import extract_raw_tables

class MoneyConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MS Money to CSV converter")

        self.config_file = "MNY_config.txt"
        self.config_data = {}
        self.load_config()

        self.create_widgets()

    def load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                for line in f:
                    if line.strip() and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        self.config_data[key.strip()] = value.strip()
        else:
            self.config_data = {}

    def save_config(self):
        with open(self.config_file, 'w') as f:
            for key, value in self.config_data.items():
                f.write(f"{key}={value}\n")

    def create_widgets(self):
        tk.Label(self.root, text="MNY File Path:").grid(row=0, column=0, padx=10, pady=5)
        self.mny_file_path_var = tk.StringVar(value=self.config_data.get('MNY_FILE_PATH', ''))
        tk.Entry(self.root, textvariable=self.mny_file_path_var, width=50).grid(row=0, column=1, padx=10, pady=5)
        tk.Button(self.root, text="Browse", command=self.browse_mny_file).grid(row=0, column=2, padx=10, pady=5)

        tk.Label(self.root, text="Output Directory:").grid(row=1, column=0, padx=10, pady=5)
        self.output_dir_var = tk.StringVar(value=self.config_data.get('OUTPUT_DIR', ''))
        tk.Entry(self.root, textvariable=self.output_dir_var, width=50).grid(row=1, column=1, padx=10, pady=5)
        tk.Button(self.root, text="Browse", command=self.browse_output_dir).grid(row=1, column=2, padx=10, pady=5)

        tk.Label(self.root, text="Include Raw Tables:").grid(row=2, column=0, padx=10, pady=5)
        self.raw_tables_var = tk.BooleanVar(value=self.config_data.get('RAW_TABLES', 'FALSE').lower() == 'true')
        tk.Checkbutton(self.root, variable=self.raw_tables_var).grid(row=2, column=1, padx=10, pady=5)

        tk.Button(self.root, text="Convert", command=self.convert).grid(row=3, column=0, columnspan=3, padx=10, pady=20)

    def browse_mny_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Money Files", "*.mny")])
        if file_path:
            self.mny_file_path_var.set(file_path)

    def browse_output_dir(self):
        dir_path = filedialog.askdirectory()
        if dir_path:
            self.output_dir_var.set(dir_path)

    def convert(self):
        self.config_data['MNY_FILE_PATH'] = self.mny_file_path_var.get()
        self.config_data['OUTPUT_DIR'] = self.output_dir_var.get()
        self.config_data['RAW_TABLES'] = str(self.raw_tables_var.get()).upper()

        if not self.validate_inputs():
            return

        self.save_config()

        self.run_mny2qif()
        self.run_qif_to_csv()
        if self.config_data['RAW_TABLES'] == 'TRUE':
            self.run_extract_raw_tables()

        messagebox.showinfo("Success", "Conversion completed successfully!")
        sys.exit() # Exit the program after successful conversion

    def validate_inputs(self):
        if not os.path.exists(self.config_data['MNY_FILE_PATH']):
            messagebox.showerror("Error", "MNY File does not exist.")
            return False

        output_dir = self.config_data['OUTPUT_DIR']
        if not os.path.isdir(output_dir):
            response = messagebox.askyesno("Directory Not Found", f"The output directory '{output_dir}' does not exist. Would you like to create it?")
            if response:
                try:
                    os.makedirs(output_dir, exist_ok=True)
                    messagebox.showinfo("Success", f"Output directory '{output_dir}' created successfully.")
                except OSError as e:
                    messagebox.showerror("Error", f"Failed to create directory '{output_dir}': {e}")
                    return False
            else:
                return False

        return True

    def run_mny2qif(self):
        #from mny2qif_modified import main as mny2qif_main
        mny2qif_main(self.config_data['MNY_FILE_PATH'], self.config_data['OUTPUT_DIR'])

    def run_qif_to_csv(self):
        #from QIFtoCSV_modified import main as qif_to_csv_main
        #qif_to_csv_main(self.config_data['OUTPUT_DIR'], self.config_data['OUTPUT_DIR'])
        qif_dir = self.config_data['OUTPUT_DIR']
        qif_files = [os.path.join(qif_dir, f) for f in os.listdir(qif_dir) if f.endswith('.qif')]
        if qif_files:
            print(f"QIF Files to Convert: {qif_files}")
            qif_to_csv_main(qif_files=qif_files, csv_dir=qif_dir)
        else:
            print("No QIF files found in the output directory.")

    def run_extract_raw_tables(self):
        #from extract_raw_tables import extract_raw_tables
        extract_raw_tables(self.config_data['MNY_FILE_PATH'], self.config_data['OUTPUT_DIR'])

if __name__ == "__main__":
    root = tk.Tk()
    app = MoneyConverterApp(root)
    root.mainloop()