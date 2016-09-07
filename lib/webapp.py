from lib import *

class Webapp(Project):
    name = "Webapp"

    def __init__(self, args):
        Project.__init__(self,args)

    def code_build(self):
        print("Building code {}".format(self.name))

    def content_build(self):
        print("Building content {}".format(self.name))

    def static_export(self):
        print("Exporting static site {}".format(self.name))
