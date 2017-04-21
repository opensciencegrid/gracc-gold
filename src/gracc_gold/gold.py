
"""
Module for interacting with Gold

Takes a summarized Gratia job and either charges or refunds it.
"""

from datetime import datetime, timedelta
from dateutil import parser
import logging
import os
import time
import re


log = logging.getLogger("gracc_gold.gold")
logname = None

def setup_env(cp):
    global logname
    logname = cp.get("main", "log")
    gold_home = cp.get("main", "gold_home")
    #if not os.path.exists(gold_home):
    #    raise Exception("GOLD_HOME %s does not exist!" % gold_home)
    os.environ['GOLD_HOME'] = gold_home
    paths = os.environ['PATH'].split(":")
    paths.append(os.path.join(gold_home, "bin"))
    paths.append(os.path.join(gold_home, "sbin"))
    # join the elements in paths by ;
    os.environ['PATH'] = ":".join(paths)


def get_digits_from_a_string(string1):
    '''
    The number of processors or node_count sometimes shows 1L or None.
    This function only read digits from a given string,
    and return the corresponding number in a string format.
    For example, 1L will return "1".
    None will return "1". 
    123L will return "123".
    '''
    if string1 is None:
        return "1"
    if (type(string1) is int):
        return str(int(string1))
    digitsofstring1 = ""
    for i in range(len(string1)):
        if string1[i]>='0' and string1[i]<='9':
            digitsofstring1 += string1[i]
    if digitsofstring1 == "":
        numberofstring1 = "1"
    else:
        numberofstring1 = digitsofstring1
    return numberofstring1


def call_gcharge(job):
    '''
    job has the following information 
    dbid, resource_type, vo_name, user, charge, wall_duration, cpu, node_count, njobs, 
    processors, endtime, machine_name, project_name

    2012-05-09 20:19:46 UTC [yzheng@osg-xsede:~/mytest]$ gcharge -h
    Usage:
    gcharge [-u user_name] [-p project_name] [-m machine_name] [-C
    queue_name] [-Q quality_of_service] [-P processors] [-N nodes] [-M
    memory] [-D disk] [-S job_state] [-n job_name] [--application
    application] [--executable executable] [-t charge_duration] [-s
    charge_start_time] [-e charge_end_time] [-T job_type] [-d
    charge_description] [--incremental] [-X | --extension property=value]*
    [--debug] [-?, --help] [--man] [--quiet] [-v, --verbose] [-V, --version]
    [[-j] gold_job_id] [-q quote_id] [-r reservation_id] {-J job_id}
    '''
    args = ["gcharge"]
    if "user" in job:
        args += ["-u", job['user']]
    if "project_name" in job:
        args += ["-p", job['project_name']]
    args += ["-m", "grid1.osg.xsede"]
    if 'queue' not in job:
        job['queue'] = "condor"
    args += ["-C", job['queue']]

    originalnumprocessors = job['processors']
    job['processors'] = get_digits_from_a_string(originalnumprocessors)
    args += ["-P", job['processors']]
    
    originalnodecount = job['nodes']
    job['nodes'] = get_digits_from_a_string(originalnodecount)
    args += ["-N", job['nodes']]

    # job id is just a timestamp, but make sure it is unique
    time.sleep(2)
    job_id = str(time.time())
    job_id = re.sub("\..*", "", job_id)
    args += ["-J", job_id]

    if not "wall_duration" in job:
        job['charge'] = "3600" # default 3600 seconds, which is 1 hour
    else:
        job['charge'] = str(int(job['wall_duration'])) # job['wall_duration'] is in seconds
    args += ["-t", job['charge']]
    
    # walltime is the same as the charge
    args += ["-X", "WallDuration=" + str(job['charge'])] 

    # if there is no endtime, force the end time to be now
    if job['end_time'] is None:
        today = datetime.today()
        dt = datetime(today.year, today.month, today.day, today.hour, today.minute, today.second)
        job['end_ime'] = str(dt)
    end_dt = parser.parse(job['end_time'])
    
    # we need a starttime for amiegold - let's just put it 24 hours before the endtime
    start_dt = end_dt - timedelta(1,0)
    
    # queue time is also required, but does not make much sense for summary jobs    
    args += ["-X", "QueueTime=\""+ str(start_dt) +"\""]
    args += ["-X", "StartTime=\""+ str(start_dt) +"\""]
    args += ["-X", "EndTime=\""+ str(end_dt) +"\""]

    log.debug("gcharge args are: " + str(args))

    pid = os.fork()
    fd = open(logname, 'a')
    fdfileno = fd.fileno()
    if pid == 0:
        execvpstatus = 0
        try:
            os.dup2(fdfileno, 1)
            os.dup2(fdfileno, 2)
            execvpstatus = os.execvp("gcharge", args)
        except:
            log.error("os.execvp failed; error code is "+str(execvpstatus))
            os._exit(1)
    status = 0
    pid2 = 0
    while pid != pid2:
        pid2, status = os.wait()
    if status == 0:
        log.debug("gcharge " + str(args)+"\nJob charge succeed ...")
    else:
        log.error("gcharge " + str(args)+"\nJob charging failed; Error code is "+str(status))

    return status

