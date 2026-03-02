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
