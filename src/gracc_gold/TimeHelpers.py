
import time
from datetime import datetime
from calendar import timegm
import sys
import re
    

def date_to_epoch(s):
    """
    converts a give date (2017-04-01T00:00:00Z) to epoch
    """
    s = re.sub("\..*", "Z", s)
    return timegm(time.strptime(s.replace('Z', 'GMT'), "%Y-%m-%dT%H:%M:%S%Z"))
    
    
def epoch_to_date(secs):
    """
    convert a unix timestamp to date
    """
    return datetime.utcfromtimestamp(secs).isoformat() + "Z"
