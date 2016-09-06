# monitoring utilities

from datetime import date
import shutil
import sys
import errno
import re
import os
from lib import *


class JenkinsHost(UbuntuHost):
    name = "Jenkins Ubuntu Host"

    def __init__(self, cmd=None):
        UbuntuHost.__init__(self, cmd)

    def check_jenkins_plugins(self):
        print('Checking Jenkins plugins')
        ok = True
        rplugins = {'svn-importer-plugin.jpi': 1, 'build-blocker-plugin.jpi': 1,
                    'purge-build-queue-plugin.jpi': 0, 'purge-job-history.jpi': 0,
                    'push-master-flash.jpi': 0}
        iplugins = []
        mplugins = []
        fplugins = []
        # get list of installed plugins
        for file in os.listdir('/var/lib/jenkins/plugins'):
            if re.match('.+\.jpi', file):
                iplugins.append(file)
        for plugin, required in rplugins.items():
            found = False
            for iplugin in iplugins:
                if re.match(iplugin, plugin):
                    found = True
                    fplugins.append(iplugin)
                    break
            if not found:
                if required:
                    print('ERROR: Missing mandatory plugin {}'.format(plugin))
                    ok = False
                mplugins.append(plugin)
        if fplugins:
            print('Required plugins found {}'.format(fplugins))
        if mplugins:
            print('WARNING: Required plugins not found {}'.format(mplugins))

        # always return True instead of value of ok until check is treated as major
        return ok

    def purge_jenkins_build_logs(self, days):
        print('Purging Jenkins build logs over {} days old'.format(days))
        ok = True
        today = date.today()
        # find list of jobs
        jpath = '/var/lib/jenkins/jobs'
        if not os.path.exists(jpath):
            exit_err('Jenkins build logs path {} does not exist'.format(jpath))
        for job in os.listdir(jpath):
            old_dirs = []
            print('Processing build logs of job {}'.format(job))
            blpath = os.path.join(jpath, job, 'builds')
            if not os.path.exists(blpath):
                print("Skipping because job has no history".format(job))
                continue
            for bdir in os.listdir(blpath):
                if not re.match('\d+', bdir):
                    continue
                else:
                    full_dir = os.path.join(blpath, bdir)
                    try:
                        os.stat(full_dir)
                    except OSError as e:
                        if e.errno:
                            print('Exception found: {}'.format(e))
                            print('Skipping purge for {}'.format(full_dir))
                            continue
                    dir_date = date.fromtimestamp(os.path.getmtime(full_dir))
                    if (today - dir_date).days > int(days):
                        old_dirs.append(bdir)
            if not old_dirs:
                continue
            print('Found older builds: {}'.format(old_dirs))
            for odir in old_dirs:
                full_dir = os.path.join(blpath, odir)
                if os.path.islink(full_dir):
                    print("Removing symlink {}".format(full_dir))
                    os.unlink(full_dir)
                else:
                    print("Removing dir {}".format(full_dir))
                    shutil.rmtree(full_dir)
        return ok


class JenkinsMonitoring(Utils):
    name = "Jenkins Monitoring"
    failed_fcts = []
    passed_fcts = []

    def __init__(self, args):
        print("Creating %s" % self.name)
        self.args = args
        self.cmd = Command()
        self.host = JenkinsHost(self.cmd)

    def check_jenkins_plugins(self):
        ok = self.host.check_jenkins_plugins()
        fct = sys._getframe().f_code.co_name
        if not ok:
            self.failed_fcts.append(fct)
        else:
            self.passed_fcts.append(fct)

    def check_inodes(self):
        threshold = 90  # arbitrarily set threshold to 90%
        dv = os.environ.get('INODE_THRESHOLD')
        if dv:
            # set to whatever value defined in the environment
            threshold = dv
        ok = self.host.check_inodes(threshold)
        fct = sys._getframe().f_code.co_name
        if not ok:
            self.failed_fcts.append(fct)
        else:
            self.passed_fcts.append(fct)

    def check_diskspace(self):
        threshold = 90  # arbitrarily set threshold to 90%
        dv = os.environ.get('DISKSPACE_THRESHOLD')
        if dv:
            # set to whatever value defined in the environment
            threshold = dv
        ok = self.host.check_diskspace(threshold)
        fct = sys._getframe().f_code.co_name
        if not ok:
            self.failed_fcts.append(fct)
        else:
            self.passed_fcts.append(fct)

    def purge_jenkins_build_logs(self):
        days = 45
        dv = os.environ.get('JENKINS_BUILD_LOG_PURGE_DAYS')
        if dv:
            # set to whatever value defined in the environment
            days = dv
        ok = self.host.purge_jenkins_build_logs(days)
        fct = sys._getframe().f_code.co_name
        if not ok:
            self.failed_fcts.append(fct)
        else:
            self.passed_fcts.append(fct)

    def summary_report(self):
        ffs = self.failed_fcts
        pfs = self.passed_fcts
        print('\nJenkins Monitoring Summary Report -')
        print('{} passed functions: {}'.format(len(pfs), pfs))
        if ffs:
            print('{} failed functions: {}'.format(len(ffs), ffs))
            exit(1)

    def execute(self):
        self.load_properties()
        self.check_diskspace()
        if not self.args.debug:
            self.check_inodes()
            self.check_jenkins_plugins()
            self.purge_jenkins_build_logs()
        self.summary_report()
