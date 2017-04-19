#!/usr/bin/env python3

import sys
import os
import argparse
# below import statement requires 'export PYTHONPATH=.' in shell env
from lib import *


def parse_args():
    parser = argparse.ArgumentParser(description='Jenkins Monitoring and Provisioning')
    parser.add_argument('-v', '--verbose', help="increase verbosity", action="store_true")
    parser.add_argument('--property_file',
                        help='the file that has project properties to be substituted into job configurations')
    parser.add_argument('--dryrun', action='store_true',
                        help="show what would be done but do not perform the underlying functions "
                             "one such as deleting real files etc..")
    parser.add_argument('-d', '--debug', action='store_true', help='for development purpose only')
    args = parser.parse_args()

    if args.debug:
        print('Running in debug mode')
    return args


def main():
    args = parse_args()
    jmon = JenkinsMonitoring(args)
    jmon.execute()


if __name__ == "__main__":
    main()
