# Run Summary viewer
This program create a run summary of data taken by CAEN CoMPASS (>ver. 2.4.0). Run name taken from directory names in ```./DAQ/```. Start and Stop timing is taken from ```./<run_name>/<run_name>_info.txt```.
The run summary is showing on the web server using ```streamlit``` and csv summary can be downloaded from the web brower.

# Preparation
```shell
pip install -r requirements.txt
```

# Usage

```shell
streamlit run runsummary.py
```

# Optional custom editable columns

You can add extra editable columns to the table by creating a file named `editable_columns.txt` in the same directory as `run_summary.py`.

- If this file does not exist, only `Comment` is editable.
- If this file exists, each listed field is added as an editable column.

Supported formats:

- One field per line
- Comma-separated fields

Example (`editable_columns.txt`):

```text
Beam
Target
```

or

```text
Beam, Target
```
