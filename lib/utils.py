# utilities
import subprocess
import datetime
import os
import re


# command class based on subprocess.Popen
class Command:
    def __init__(self):
        print("Creating Command")

    def run(self, cmd):
        # reset variables for every run
        self.last_stdout = None
        self.last_stderr = None
        self.last_status = None
        timestamp = '{:%Y-%m-%d %H:%M:%S}'.format(datetime.datetime.now())
        print("%s: %s" % (timestamp, cmd))
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (out, err) = proc.communicate()
        if out:
            out = str(out, 'utf-8').rstrip('\n')
            print(out)
            self.last_stdout = out
        if err:
            err = str(err, 'utf-8').rstript('\n')
            print(err)
            self.last_stderr = err

        self.last_status = proc.returncode
        return self.last_status


class Host():
    name = "Generic Host"

    def __init__(self, cmd=None):
        print("Creating %s" % self.name)
        if not cmd:
            self.cmd = Command()
        else:
            self.cmd = cmd


class MacHost(Host):
    name = "Mac Host"

    def __init__(self, cmd=None):
        Host.__init__(self, cmd)

    def check_inodes(self, threshold):
        print('Checking % of inodes in used (threshold = {}%)'.format(threshold))
        ok = True
        self.cmd.run('df -i')
        for line in self.cmd.last_stdout.split('\n'):
            if re.match('^map', line):
                continue
            (pt, foo, foo, foo, foo, foo, foo, piu, mnt) = re.split('\s+', line, 8)
            if not re.match('\d+\%', piu):
                continue
            p = re.compile('%')
            piu = p.sub('', piu)
            if int(piu) > threshold:
                print('ERROR: Partition {} has {}% of inodes'.format(pt, piu))
                ok = False
        return ok

    def check_diskspace(self, threshold):
        print('Checking % of diskspace per partition (threshold = {}%)'.format(threshold))
        ok = True
        self.cmd.run('df -h')
        for line in self.cmd.last_stdout.split('\n'):
            if re.match('^map', line):
                continue
            (pt, foo, foo, foo, foo, foo, foo, piu, mnt) = re.split('\s+', line, 8)
            if not re.match('\d+\%', piu):
                continue
            p = re.compile('%')
            piu = p.sub('', piu)
            if int(piu) > threshold:
                print('ERROR: Partition {} has {}% of diskspace'.format(pt, piu))
                ok = False
        return ok


class UbuntuHost(Host):
    name = "Ubuntu Host"

    def __init__(self, cmd=None):
        Host.__init__(self, cmd)

    def check_inodes(self, threshold):
        print('Checking % of inodes per partition (threshold = {}%)'.format(threshold))
        ok = True
        self.cmd.run('df -i')
        for line in self.cmd.last_stdout.split('\n'):
            (pt, foo, foo, foo, piu, mnt) = re.split('\s+', line, 5)
            if not re.match('\d+\%', piu):
                continue
            p = re.compile('%')
            piu = p.sub('', piu)
            if int(piu) > int(threshold):
                print('ERROR: Partition {} has {}% of inodes'.format(pt, piu))
                ok = False
        return ok

    def check_diskspace(self, threshold):
        print('Checking % of diskspace per partition (threshold = {}%)'.format(threshold))
        ok = True
        self.cmd.run('df -h')
        for line in self.cmd.last_stdout.split('\n'):
            (pt, foo, foo, foo, piu, mnt) = re.split('\s+', line, 5)
            if not re.match('\d+\%', piu):
                continue
            p = re.compile('%')
            piu = p.sub('', piu)
            if int(piu) > int(threshold):
                print('ERROR: Partition {} has {}% of diskspace'.format(pt, piu))
                ok = False
        return ok

def exit_err(msg):
    print('ERROR: {}'.format(msg))
    exit(1)


def create_host():
    print('Determining host type')
    proc = subprocess.Popen('uname -a', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (out, err) = proc.communicate()
    if err:
        exit_err('Unable to determine host type')
    if out:
        out = str(out, 'utf-8').rstrip('\n')  # have to convert 'byte'
    if re.match('Linux.+Ubuntu', out):
        host = UbuntuHost()
    elif re.match('Darwin.+Darwin', out):
        host = MacHost()
    else:
        host = Host()
    return host


# generic utils class
class Utils():
    name = "Utils"

    def __init__(self, args):
        print("Creating %s" % self.name)
        self.args = args
        self.host = create_host()

    def load_properties(self, pfile=None):
        file = os.environ.get('PROPERTY_FILE')
        if self.args.property_file:
            file = self.args.property_file
        if file:
            print("Loading properties from %s" % file)
            separator = "="
            keys = {}

            with open(file) as f:
                for line in f:
                    if separator in line:
                        name, value = line.split(separator, 1)
                        # Assign key value pair to dict
                        # strip() removes white space from the ends of strings
                        keys[name.strip()] = value.strip()
                print(keys)
                for name, value in keys.items():
                    env_value = os.environ.get(name)
                    if env_value:
                        print(
                            "Not loading {} with {} as it is already set to {}".format(name, value, env_value))
                    else:
                        print("Loading %s as value %s" % (name, value))
                        os.environ[name] = value
                        # print(os.environ)

    def run_script(self, script, body=None):
        if body:
            f = open(script, 'w')
            f.write(body)
            f.close()
            os.chmod(script, 0o755)

        print("Running script %s" % script)
        self.cmd.run(script)

    def load_server_list(self, file):
        # list of servers and format
        # <server> / <type> / <setting1=a, setting2=b, ...>
        print("Loading Server List [%s]" % file)
