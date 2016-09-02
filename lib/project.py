# generic project class
from lib import *

class Project:
    name = "Generic"  # placeholder only, should be defined by subclass

    def __init__(self, args):
        print("Creating %s" % self.name)
        self.args = args
        self.utils = Utils(args)  # create Utils for use throughout class
        self.utils.load_properties()

    def commit(self):
        print("Building (commit) %s".format(self.name))

    def component(self):
        print("Building (component) {}".format(self.name))

    def deploy(self):
        print("Deploying {}".format(self.name))

    def certify(self):
        print("Certifying {}".format(self.name))

    def execute(self):
        print("Executing {}".format(self.name))
        ok = True
        action = self.args.action
        type = self.args.project_type
        if action:
            print('Perform {} action'.format(action))
            script = 'script' + '/' + type + '/' + action + '.py'
            cmd = self.utils.host.cmd
            ok = cmd.run(script)
        return ok