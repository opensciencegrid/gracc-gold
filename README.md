# gracc-gold

This script is meant to synchronize and summarize job records from the OSG
GRACC system into GOLD.

Due to the Python dependencies of ES, we are now running this under the gold
account. To install, as the gold user:

```
export PATH=/home/gold/python-3.6.1/bin:$PATH
python3 setup.py install --prefix=/home/gold/software/gracc-gold
```

