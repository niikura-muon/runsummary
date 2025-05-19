# Run Summary viewer
This program create a run summary of data taken by CAEN CoMPASS (>ver. 2.4.0). Run name taken from directory names in ```./DAQ/```. Start and Stop timing is taken from ```./xxx/xxx_info.txt```. Currently only ja_JP.UTF-8 time locale is assumed.
The run summary is showing on the web server using ```streamlit``` and csv summary can be downloaded from the web brower.

# Preparation
```shell
$ pip install -r requirements.txt
```

# Usage

```shell
$ streamlit run runsummary.py
```
