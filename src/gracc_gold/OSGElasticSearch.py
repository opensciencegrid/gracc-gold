'''
Builds an ES query based on the given config file section

@author: rynge
'''

import logging
import time
from datetime import datetime
from calendar import timegm
import sys
import re

from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search

from pprint import pprint, pformat

import urllib3
urllib3.disable_warnings()

from TimeHelpers import *

log = logging.getLogger("gracc_gold")


class OSGElasticSearch(object):
    '''
    Builds an ES query based on the given config file section
    '''

    def __init__(self, conf):
        '''
        
        :param conf:
        :param state:
        '''
        
        self.conf = conf

        
    def query(self, conf_section, start_time):
        '''
        Queries ES for the data configured in the conf_section of the config file
        
        :param conf:
        :param conf_section:
        '''
        
        # only do this months index - small problem when crossing month
        # boundaries, but the data ignored is minor
        # example: gracc.osg.raw3-2016.11
        now = datetime.utcnow()
        index = 'gracc.osg.raw3-' + now.strftime("%Y.%m")
       
        # figure out end date - query for 1 week max
        start_ts = date_to_epoch(start_time)
        end_ts = start_ts + (7*24*60*60)
        end_time = epoch_to_date(end_ts)
        
        log.info("Querying for data between " + start_time + " and " + end_time)

        wildcardProbeNameq = 'condor:*'
        if self.conf.has_option(conf_section, "probe"):
            wildcardProbeNameq = 'condor:' + self.conf.get(conf_section, "probe")
            
        wildcardProjectName = '*'
        if self.conf.has_option(conf_section, "project_name"):
            wildcardProjectName = self.conf.get(conf_section, "project_name")
            
        # Elasticsearch query and aggregations
        s = Search(using=self._establish_client(), index=index) \
                .query("wildcard", ProbeName=wildcardProbeNameq) \
                .filter("wildcard", ProjectName=wildcardProjectName) \
                .filter("range", ** {'@received': {'gt': start_time, "lte": end_time}}) \
                .filter("term", ResourceType="Payload")[0:0]
        # Size 0 to return only aggregations
    
        # is this needed with the buckets below?
        s.sort('@received')
        
        unique_terms = [["ProjectName", "N/A"], ["LocalUserId", "N/A"], ["NodeCount", 1], ["Processors", 1]]
        # If the terms are missing, set as "N/A"
        curBucket = s.aggs.bucket(unique_terms[0][0], 'terms', field=unique_terms[0][0], missing=unique_terms[0][1], size=(2**31)-1)
        new_unique_terms = unique_terms[1:]
        for term in new_unique_terms:
            curBucket = curBucket.bucket(term[0], 'terms', field=term[0], missing=term[1], size=(2**31)-1)
            
        # Metric aggs
        metrics = ["ReceivedTimeFirst", "ReceivedTimeLast", "WallDurationTotal"]
        curBucket.metric('ReceivedTimeFirst', 'min', field='@received') \
                 .metric('ReceivedTimeLast', 'max', field='@received') \
                 .metric('WallDurationTotal', 'sum', field='WallDuration')

        #log.debug(pformat(s.to_dict()))

        # FIXME: improve error handling
        try:
            response = s.execute()
            if not response.success():
                raise
            results = response.aggregations
        except Exception as e:
            print(e, "Error accessing Elasticsearch")
            sys.exit(1)

        log.debug(pformat(results.to_dict()))
        
        # build our return data structure - it is a dict with some metadata, and then the actual data
        info = {}
        info["item_count"] = 0
        info["max_date_value"] = 0
        info["max_date_str"] = ""
        info["data"] = []
        for project in (results.ProjectName.buckets):
            for user in (project.LocalUserId.buckets):
                for nodes in (user.NodeCount.buckets):
                    for processors in (nodes.Processors.buckets):
                        info["item_count"] = info["item_count"] + 1
                        # track the largest date in the whole query - used as starting point for the next round
                        if processors.ReceivedTimeLast.value > info["max_date_value"]:
                            info["max_date_value"] = processors.ReceivedTimeLast.value
                            info["max_date_str"] = processors.ReceivedTimeLast.value_as_string
                        data = {}
                        data["project_name"] = project.key
                        data["user"] = user.key
                        data["nodes"] = int(nodes.key)
                        data["processors"] = int(processors.key)
                        data["wall_duration"] = int(processors.WallDurationTotal.value)
                        
                        data["end_time"] = processors.ReceivedTimeLast.value_as_string
                        # we have to make up a start time, but it can't be too far in the past as an allocation
                        # might not have started yet - 24 hours is probably safe if the values are too large
                        delta = min(processors.ReceivedTimeLast.value/1000 - processors.ReceivedTimeFirst.value/1000, 24 * 60 * 60)
                        start_dt = datetime.utcfromtimestamp(processors.ReceivedTimeLast.value/1000 - delta)
                        data["start_time"] = start_dt.isoformat()

                        # let's clean up the dates
                        data["start_time"] = re.sub("T", " ", data["start_time"][0:19])
                        data["end_time"] = re.sub("T", " ", data["end_time"][0:19])

                        # do we really care about the .000Z part? let's at least be consistent
                        #if len(data["start_time"]) == 19:
                        #    data["start_time"] = data["start_time"] + ".000Z"
                            
                        # some fields can be overridden in the config file for each section
                        if self.conf.has_option(conf_section, "override_user"):
                            data["user_overridden"] = data["user"]
                            data["user"] = self.conf.get(conf_section, "override_user")
                        if self.conf.has_option(conf_section, "override_project_name"):
                            data["project_name_overridden"] = data["project_name"]
                            data["project_name"] = self.conf.get(conf_section, "override_project_name")
                        
                        info["data"].append(data)
        
        # the rest of this program uses unix timestamps
        # no data for the time range?
        if info["max_date_str"] == "":
            # is the end time in the future?
            if end_ts > time.time():
                info["max_date_str"] = epoch_to_date(time.time())
            else:
                info["max_date_str"] = end_time
        info["max_date_epoch"] = date_to_epoch(info["max_date_str"])
    
        #pprint(info, indent=4)
        return info
    
        
    def _establish_client(self):
        '''
        Initialize and return the elasticsearch client
        '''
        client = Elasticsearch([self.conf.get("es", "url")],
                               use_ssl=self.conf.getboolean("es", "use_ssl"),
                               verify_certs=False,
                               timeout=self.conf.getint("es", "timeout"))
        return client
        
    

    
