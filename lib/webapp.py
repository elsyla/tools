from lib import *

class Webapp(Project):
    name = "Webapp"

    def __init__(self, args):
        Project.__init__(self,args)

    def code_build(self):
        print("Building code {}".format(self.name))
        return True

    def content_build(self):
        print("Building content {}".format(self.name))
        return True

    def static_export(self):
        print("Exporting static site {}".format(self.name))
        return True

    def execute(self):
        print("Executing {}".format(self.name))
        ok = True
        function = self.args.function
        type = self.args.project_type
        if function:
            # execute build function as defined by class method
            ok = getattr(Webapp, function)(self)
        return ok