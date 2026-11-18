Certainly! Below is the complete README.md file in a formatted Markdown block that you can copy and paste into a `.md` file:

---
# MS Money to CSV Conversion Suite

Converts a Microsoft Money `.mny` file to CSV files suitable for import into tools like PowerBI. 
**Thanks to [@ThisNoName](https://github.com/ThisNoName/running-out-of-money) for the python-native foundational database work** 

*Note:  This code was supported and debugged with the help of AI.*

The conversion process involves three main steps:

1. **`MNYtoCSV.py`**: Main program entrypoint - launches a GUI.
2. **`mny2qif_modified.py`**: Converts the `.mny` file to QIF files for each account.
3. **`QIFtoCSV_modified.py`**: Converts the QIF files to CSV files.
4. **`extract_raw_tables.py`**: (Optional) Extracts all raw tables from the `.mny` file for debugging and troubleshooting.

## Files

| File | Purpose |
| --- | --- |
| `jet4.py` | Read-only Jet4/MSISAM reader: pages, table definitions, row decoding |
| `money_modified.py` | Modified Money schema interpretation and QIF rendering |
| `mny2qif_modified.py` | Converts `.mny` to QIF command line entry point |
| `QIFtoCSV_modified.py` | Converts QIF to CSV command line entry point |
| `extract_raw_tables.py` | Extracts raw tables from the `.mny` file |
| `compare_qifs.py` | Compares two QIF files transaction by transaction |
| `MNYtoCSV.py` | Main program entry point with GUI and batch processing |
| `requirements.txt` | List of required Python packages |

## Typical Use

### 1. Conversion via GUI

1. Run `MNYtoCSV.py`:
    ```bash
    python MNYtoCSV.py
    ```
2. Use the GUI to:
    - Select the `.mny` file.
    - Choose the output directory.
    - Optionally, include raw table extraction.
3. Click "Convert" to start the process.

### 2. Conversion via CLI

#### Step 1: Convert `.mny` to QIF
```bash
python mny2qif_modified.py <MNY_FILE_PATH> -o <OUTPUT_DIR>
```

#### Step 2: Convert QIF to CSV (launches it's only Standalone GUI)
```bash
python QIFtoCSV_modified.py
```

#### Step 3: Extract Raw Tables (Optional)
```bash
python extract_raw_tables.py <MNY_FILE_PATH> <OUTPUT_DIR>
```

## Detailed CLI Usage

### `mny2qif_modified.py`

```bash
python mny2qif_modified.py <MNY_FILE_PATH> [-o <OUTPUT_DIR>]
```

- `<MNY_FILE_PATH>`: Path to the input `.mny` file.
- `-o <OUTPUT_DIR>`: Output directory for the QIF files (default: current directory).

### `QIFtoCSV_modified.py` (launches it's only Standalone GUI)

```bash
python QIFtoCSV_modified.py
```

### `extract_raw_tables.py`

```bash
python extract_raw_tables.py <MNY_FILE_PATH> <OUTPUT_DIR>
```

- `<MNY_FILE_PATH>`: Path to the input `.mny` file.
- `<OUTPUT_DIR>`: Output directory for the raw tables.

### `compare_qifs.py`

```bash
python compare_qifs.py <FILE1> <FILE2> -o <OUTPUT_DIR> [--strict]
```

- `<FILE1>`: Path to the first QIF file (e.g., MS Money QIF).
- `<FILE2>`: Path to the second QIF file (e.g., mny2qif output QIF).
- `-o <OUTPUT_DIR>`: Output directory for the comparison reports.
- `--strict`: Also compare fields like Action, Security, Shares, Price, Payee, Category, and Splits.

## GUI Features

- **MNY File Path**: Browse and select the `.mny` file.
- **Output Directory**: Browse and select the output directory for the converted files.
- **Include Raw Tables**: Option to extract raw tables for debugging.
- **Convert**: Start the conversion process.

## Dependencies

Beyond standard python libraries, the program only requires `pandas` for the extract_raw_tables.py file.
Install the required Python packages using `pip`:
```bash
pip install -r requirements.txt
```

## Notes

- The conversion process ensures that all transactions and categories are correctly mapped to their respective QIF and CSV formats.
- The GUI and CLI options provide flexibility for users to choose their preferred workflow.
- The `extract_raw_tables.py` script is optional and useful for debugging the parsing of the `.mny` file.
