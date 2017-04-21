
"""
Maintains the state of a GraccGold map on disk
"""

import os
import logging

import simplejson

log = logging.getLogger("gracc_gold")


class MapState(object):

    def __init__(self, conf, map_name):
        """
        sets up the state file for a map
        """
        self.conf = conf
        self.file_name = conf.get("main", "state_dir") + "/" + map_name
        
        # read the state
        try:
            fp = open(self.file_name, "r")
        except:
            raise Exception("Unable to open " + self.file_name + " for reading")
        self.state = simplejson.load(fp)
        fp.close()
        
        # also make sure can write to it
        self.save()
        
        
    def get_ts(self):
        """
        get the current ts from the state
        """
        return self.state["last_ts"]
    

    def update_ts(self, ts):
        """
        update the ts for this map
        """
        self.state["last_ts"] = ts
        self.save()


    def save(self):
        """
        saves the current state to the file system
        """
        try:
            fp = open(self.file_name, "w")
        except Exception as e:
            raise Exception("Unable to open " + self.file_name + " for writing: " + str(e))
        try:
            fp.write(simplejson.dumps(self.state))
        except:
            raise Exception("Unable to write data to " + self.file_name)
        try:
            os.fsync(fp.fileno())
            fp.close()            
        except:
            raise Exception("Unable to fsync " + self.file_name)
            
            
            
            
