#!/usr/bin/env python3

# import modules and classes

import sys
import os
import re
import argparse
# below import statement requires 'export PYTHONPATH=.' in shell env
from lib import *


def parse_args():
    parser = argparse.ArgumentParser(description='build the project')
    parser.add_argument('-v', '--verbose', help="increase verbosity", action="store_true")
    parser.add_argument('--property_file',
                        help='file containing project properties')
    parser.add_argument('--project_type', help='project type [webapp, ...]')
    parser.add_argument('--action', help='perform action corresponding to script/<project_type>/<action>.py')
    parser.add_argument('--dryrun', action='store_true',
                        help="show what would be done but do not perform the actual underlying action")
    parser.add_argument('-d', '--debug', action='store_true', help='for development purpose only')
    args = parser.parse_args()
    if args.debug:
        print('Running in debug mode')
    if not args.project_type:
        print("Missing --project_type <projec_type_x>")
        exit(0)
    if not (args.action or args.script):
        print("Missing either --action <some_action> or --script <some_script>")
        exit(0)
    return args


def main():
    args = parse_args()
    if re.match('webapp', args.project_type):
        project = Webapp(args)
    else:
        exit_err("Unidentified project type")
    project.execute()


if __name__ == "__main__":
    main()
