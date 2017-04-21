
"""
Library for synchronizing ES job accounting with GOLD.

This library will connect to the ES database, summarize the accounting
records it finds, and submit the summaries to GOLD via a command-line script.

"""

import os
import time
import random
import logging
import optparse
import configparser
import sys
import re

import locking
import gold

from OSGElasticSearch import OSGElasticSearch
from MapState import MapState

log = None
logfile = None
logfile_handler = None


def parse_opts():

    parser = optparse.OptionParser(conflict_handler="resolve")
    parser.add_option("-c", "--config", dest="config",
                      help="Location of the configuration file.",
                      default="/etc/gracc-gold/gracc-gold.cfg")
    parser.add_option("-v", "--verbose", dest="verbose",
                      default=False, action="store_true",
                      help="Increase verbosity.")
    parser.add_option("-s", "--cron", dest="cron",
                      type="int", default=0,
                      help = "Called from cron; cron splay (adds a random sleep)")
    
    opts, args = parser.parse_args()

    if not os.path.exists(opts.config):
        raise Exception("Configuration file, %s, does not exist." % \
            opts.config)

    return opts, args


def config_logging(cp, opts):
    global log
    global logfile
    
    # return a logger with the specified name gracc_gold
    log = logging.getLogger("gracc_gold")

    # log to the console
    # no stream is specified, so sys.stderr will be used for logging output
    console_handler = logging.StreamHandler()

    # Log to file
    logfile = cp.get("main", "log")

    logfile_handler = logging.FileHandler(logfile)

    # default log level - make logger/console match
    # Logging messages which are less severe than logging.WARNING will be ignored
    log.setLevel(logging.WARNING)
    console_handler.setLevel(logging.WARNING)
    logfile_handler.setLevel(logging.WARNING)

    if opts.verbose: 
        log.setLevel(logging.DEBUG)
        console_handler.setLevel(logging.DEBUG)
        logfile_handler.setLevel(logging.DEBUG)

    # formatter
    formatter = logging.Formatter("[%(process)d] [%(filename)20s:%(lineno)4d] %(asctime)s %(levelname)7s:  %(message)s")
    console_handler.setFormatter(formatter)
    logfile_handler.setFormatter(formatter)
    if opts.cron == 0:
        log.addHandler(console_handler)
    log.addHandler(logfile_handler)
    log.debug("Logger has been configured")


def main():
    opts, args = parse_opts()
    conf = configparser.ConfigParser()
    conf.read(opts.config)
    config_logging(conf, opts)

    if opts.cron > 0:
        random_sleep = random.randint(1, opts.cron)
        log.info("gracc-gold called from cron; sleeping for %d seconds." % \
            random_sleep)
        time.sleep(random_sleep)

    lockfile = conf.get("main", "state_dir") + "/.lock"
    try:
        locking.exclusive_lock(lockfile)
    except Exception as e:
        log.exception("Caught an exception and the detail is: \n\"" + str(e) + "\" Exiting Now !")
        sys.exit(1)
        
    try:
        gold.setup_env(conf)
    except Exception as e:
        log.error("Caught an exception and the detail is: \n\"" + str(e) + "\" Exiting Now !")
        sys.exit(1)

    q = OSGElasticSearch(conf)
            
    # loop over all the maps defined in the conf file
    for section in conf.sections():
        
        if re.match("^map_", section):
            # we have a valid map

            state = MapState(conf, section)
            start_time = state.get_ts()

            data = q.query(section, start_time)
            
            for item in data["data"]:
                try:
                    gold.call_gcharge(item)
                except Exception as e:
                    log.error("Caught an exception and the detail is: \n  " + str(e) + "\nExiting Now !")
                    sys.exit(1)
            
            state.update_ts(data["max_date_str"])


    
    
                
