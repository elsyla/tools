#!/usr/bin/env python3
# https://media.readthedocs.org/pdf/python-jenkins/latest/python-jenkins.pdf

import re, os, sys
import jenkins
import argparse
import subprocess
import datetime
import shutil

# globals
script = 'jenkins_cli'
workdir = '/var/tmp/' + script


def parse_args():
    parser = argparse.ArgumentParser(description='Jenkins CLI')
    parser.add_argument('-q', '--quiet', help="Reduce verbosity of screen output", action="store_true")
    parser.add_argument('--property_file',
                        help='The file that has project properties to be substituted into job configurations')
    parser.add_argument('--src_jenkins_url',
                        required=True, help='Jenkins URL of source jobs')
    parser.add_argument('--dest_jenkins_url',
                        help='Jenkins URL of destination jobs.  If not specified, default value is set to '
                             'that of --src_jenkins_url.')
    parser.add_argument('--jobname_regex', required=True, help="Python regex to find matching source jobs")
    parser.add_argument('--show_jobs', action='store_true', help='Show jobs matching --jobname_regex')
    parser.add_argument('--update_jobs', action='store_true',
                        help='If specified, source jobs are updated in place with config content changed '
                             'based on --find_replace_content_pattern.')
    parser.add_argument('--find_replace_content_pattern',
                        help='Required with --update_jobs to modify job config content per <find|replace> regex.')
    parser.add_argument('--disable_jobs', action='store_true', help='Disable jobs matching --jobname_regex')
    parser.add_argument('--enable_jobs', action='store_true', help='Enable jobs matching --jobname_regex')
    parser.add_argument('--delete_jobs', action='store_true', help='Delete jobs matching --jobname_regex')
    parser.add_argument('--build_jobs', action='store_true',
                        help='Run jobs matching --jobname_regex.  Still WIP - not fully implement yet.')
    parser.add_argument('--fetch_jobs', action='store_true',
                        help='Download xml configs of jobs matching --jobname_regex to current directory.')
    parser.add_argument('--grep_jobs', action='store_true',
                        help='Grep jobs for given pattern per --grep_content_pattern')
    parser.add_argument('--grep_content_pattern',
                        help='Required with --grep_jobs to find a pattern in job config content per <pattern>')
    parser.add_argument('--clone_jobs', action='store_true',
                        help='If specified, source jobs are cloned.  New jobs are named based on either --from_'
                             'template flag or --find_replace_jobname_pattern <find|replace>.')
    parser.add_argument('--rename_jobs', action='store_true',
                        help='If specified, source jobs are renamed based on --find_replace_jobname_pattern')
    parser.add_argument('--find_replace_jobname_pattern', type=str,
                        help='If specified, names of source jobs are substituted per <find|replace> '
                             'regex to produce names of destination jobs.')
    parser.add_argument('--from_template', action='store_true',
                        help='If specified, source jobs are from standard template with naming format'
                             ' <PROJECT_TYPE>-<PROJECT_NAME>-<...>.  During job creation, PROJECT_TYPE is dropped '
                             'and PROJECT_NAME is replaced by its value defined in property file')
    parser.add_argument('--dryrun', action='store_true',
                        help="Show what would be done but do not create/update actual jobs")
    parser.add_argument('--prompt', action='store_true',
                        help="Prompt continue prior to taking action.  Useful for deleting jobs one by one"
                             " instead of all at once.")
    parser.add_argument('--user',
                        help='Login username.  If not specified at command line, you will be asked to enter '
                             'it in during runtime.')
    parser.add_argument('--password',
                        help='Login password.  If not specified at command line, you will be asked to enter '
                             'it in during runtime.  Note: If Jenkins is using CAS (as apposed to LDAP), then '
                             'use assigned Jenkins API token instead of user password.')
    args = parser.parse_args()

    if not os.path.exists(workdir):
        os.makedirs(workdir)

    # save command into history
    hfile = workdir + '/' + 'history'
    fh = open(hfile, 'a')
    fh.write(' '.join(sys.argv) + "\n")
    fh.close()

    if not (args.clone_jobs or args.update_jobs or args.disable_jobs or args.enable_jobs
            or args.build_jobs or args.delete_jobs or args.show_jobs or args.grep_jobs
            or args.rename_jobs or args.fetch_jobs):
        print(
            "Missing one of these action flags: --clone_jobs, --update_jobs, --disable_jobs, "
            "--enable_jobs, --build_jobs, --delete_jobs, --rename_jobs, --show_jobs, --grep_jobs,"
            "--fetch_jobs")
        exit(0)

    if args.grep_jobs and not args.grep_content_pattern:
        print("Flag --grep_jobs requires --grep_content_pattern <pattern>")
        exit(0)

    if args.clone_jobs and args.update_jobs:
        print("Flags --clone_jobs and --update_jobs are mutually exclusively.  Please specify only one.")
        exit(0)

    if args.update_jobs and not args.find_replace_content_pattern:
        print("Flag --update_jobs requires --find_replace_content_pattern <some_python_substituation_regex>")
        exit(0)
    if args.clone_jobs and not (args.from_template or args.find_replace_jobname_pattern or args.dest_jenkins_url):
        print(
            "Flag --clone_jobs requires at least one of these flags:"
            "--from_template flag to clone jobs from a template"
            "--find_replace_jobname_pattern <find|replace> for new jobnames in same Jenkins instance"
            "--dest_jenkins_url to clone jobs to another Jenkins instance with same or new jobnames")
        exit(0)
    if args.rename_jobs and not args.find_replace_jobname_pattern:
        print(
            "Flag --rename_jobs requires at --find_replace_jobname_pattern <find|replace> for new jobnames")
        exit(0)
    if args.find_replace_jobname_pattern and not re.match('.+\|.+', args.find_replace_jobname_pattern):
        print("Value of --find_replace_jobname_pattern should be in <find|replace> format")
        exit(0)
    if args.from_template and not args.property_file:
        print("Flag --from_template requires --property_file")
        exit(0)
    return args


def create_server_instances(args):
    uname = args.user
    pw = args.password
    pwfile = os.environ['HOME'] + '/.' + script
    if os.path.isfile(pwfile):
        for line in open(pwfile, 'r'):
            line = line.strip()
            (key, val) = line.split('=', 1)
            if key == 'USER':
                uname = val
            elif key == 'PASSWORD':
                pw = val
    else:
        print('Note: To get rid of password prompt, create {} with these line entries:'.format(
            pwfile))
        print('USER=<your_username>\nPASSWORD=<your_password>')
    if not uname:
        uname = input("Login name: ")
    if not pw:
        pw = input("Login password: ")

    url = args.src_jenkins_url
    print("Creating source Jenkins instance {}".format(url))
    server_src = jenkins.Jenkins(url, uname, pw)
    if not server_src:
        print("ERROR: Failed creating source Jenkins instance {}".format(url))
        exit(1)
    url_dest = args.dest_jenkins_url
    if not url_dest:
        return server_src, server_src
    print("Creating destination Jenkins instance {}".format(url_dest))
    server_dest = jenkins.Jenkins(url_dest, uname, pw)
    if not server_dest:
        print("ERROR: Failed creating destination Jenkins instance {}".format(url_dest))
        exit(1)
    return server_src, server_dest


def read_property_file(file):
    properties = {}
    for line in open(file, 'r'):
        line = line.rstrip()
        if re.match('^\s*#', line):
            continue
        if re.match('.+=.+', line):
            (key, val) = line.split('=', 1)
            properties[key] = val
    return properties


def substitute_vars(string, properties):
    for var in properties:
        val = properties[var]
        # special handling for IMPORT_TO_BRANCH_VALUES
        if var == 'IMPORT_TO_BRANCH_VALUE':
            val = re.sub(',', ' ', val)
            vals = re.split('\s+', val)
            # if there is more than one values, do special handling
            # ie. puttng each val into its own xml 'string' element
            if len(vals) > 1:
                val = vals[0] + '</string>'
                for val2 in vals[1:]:
                    if not re.match('.+string>$', val):
                        val = val + '</string>'
                    val = val + '\n<string>{}'.format(val2)
        string = re.sub(var, val, string)
    return string


def prompt_continue():
    input("Pressing <return> to confirm action: ")
    return True


def is_job_disabled(job, job_list):
    for ejob in job_list:
        if ejob['name'] == job:
            if ejob['color'] == 'disabled':
                return True
            else:
                return False
    print('ERROR: {} does not exist'.format(job))
    return False


def run_cmd(cmd):
    timestamp = '{:%Y-%m-%d %H:%M:%S}'.format(datetime.datetime.now())
    print("%s: %s" % (timestamp, cmd))
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (out, err) = proc.communicate()
    if out:
        out = str(out, 'utf-8').rstrip('\n')
        print(out)
    if err:
        err = str(err, 'utf-8').rstrip('\n')
        print(err)
    return proc.returncode


def main():
    # first parse arguments
    args = parse_args()

    dryrun = args.dryrun
    prompt = args.prompt
    quiet = args.quiet
    clone_jobs = args.clone_jobs
    update_jobs = args.update_jobs
    disable_jobs = args.disable_jobs
    enable_jobs = args.enable_jobs
    build_jobs = args.build_jobs
    fetch_jobs = args.fetch_jobs
    delete_jobs = args.delete_jobs
    from_template = args.from_template
    property_file = args.property_file
    rename_jobs = args.rename_jobs
    show_jobs = args.show_jobs
    grep_jobs = args.grep_jobs
    find_replace_jobname_pattern = args.find_replace_jobname_pattern
    find_replace_content_pattern = args.find_replace_content_pattern

    (server_src, server_dest) = create_server_instances(args)
    jobname_regex = args.jobname_regex
    properties = {}

    if property_file:
        properties = read_property_file(property_file)

    jobs = []
    for job in server_src.get_jobs():
        job_name = job['name']
        try:
            result = re.search(jobname_regex, job_name)
        except:
            print('ERROR: Cannot process jobname regex pattern \'{}\' - try something else.'.format(jobname_regex))
            exit(1)
        if result:
            jobs.append(job_name)

    if jobs:
        print("Found {} matching source jobs:".format(len(jobs)))
        print(jobs)
        if show_jobs:
            exit(0)
    else:
        print("No source job found")
        exit(0)

    job_list = server_dest.get_jobs()
    server_dest_url = server_dest.get_info().get('primaryView').get('url')

    if from_template:
        # get template name
        (tname, junk) = jobs[0].split('-', 1)
        views = server_src.get_views()
        for view in views:
            if not re.match('^' + tname + '.*', view['name']):
                continue
            print("Processing source view {}".format(tname))
            # assuming each template has a view
            config = server_src.get_view_config(tname)
            # save template view configuration
            file = workdir + '/' + tname + '.xml'
            fh = open(file, 'w')
            fh.write(config)
            fh.close()
            new_tname = properties['PROJECT_NAME']
            if not new_tname:
                print('ERROR: Template project must have PROJECT_NAME in property file')
                exit(1)
            # save new project view configuration
            config = re.sub(tname, new_tname, config)
            file2 = workdir + '/' + new_tname + '.xml'
            fh = open(file2, 'w')
            fh.write(config)
            fh.close()
            if not quiet:
                os.system('diff {} {}'.format(file, file2))
            if server_dest.view_exists(new_tname):
                print("Update existing view {}view/{}".format(server_dest_url, new_tname))
                if dryrun:
                    print("Dryrun mode - view won't be updated")
                else:
                    server_dest.reconfig_view(new_tname, config)
            else:
                print("Creating new view {}view/{}".format(server_dest_url, new_tname))
                if dryrun:
                    print("Dryrun mode - view won't be created")
                else:
                    server_dest.create_view(new_tname, config)
    for job in jobs:
        print("Processing source job {}".format(job))

        if disable_jobs:
            print("Disabling job")
            if dryrun:
                print("Dryrun mode - job won't be disabled")
            else:
                server_src.disable_job(job)
            continue

        if enable_jobs:
            print("Enabling job")
            if dryrun:
                print("Dryrun mode - job won't be enabled")
            else:
                server_src.enable_job(job)
            continue

        if delete_jobs:
            print("Deleting job")
            if prompt:
                prompt_continue()
            if dryrun:
                print("Dryrun mode - job won't be deleted")
            else:
                server_src.delete_job(job)
            continue

        if build_jobs:
            print("Building job")
            if dryrun:
                print("Dryrun mode - job won't be built")
            else:
                # build_jobs method needs at least one parameter to work, hence ANY_KEY
                server_src.build_job(job, parameters={'ANY_KEY': 'ANY_VALUE'}, token=None)
            continue

        # the rest is logic for either clone_jobs or update_jobs
        # get job from source Jenkins instance
        config = server_src.get_job_config(job)

        # save raw config to file
        file = workdir + '/' + job + '.xml'
        fh = open(file, 'w')
        fh.write(config)
        fh.close()

        if fetch_jobs:
            # copy job xml to current directory
            print("Fetching job")
            if dryrun:
                print("Dryrun mode - job won't be fetched to current directory")
            else:
                shutil.copyfile(file, job + '.xml')
            continue

        if grep_jobs:
            print("Grepping job")
            rc = os.system('grep {} {}'.format(args.grep_content_pattern, file))
            if rc:
                print('No match found')
            continue

        # substituted job config with properties
        config = substitute_vars(config, properties)
        # substitute job content if <find|replace> specified
        if find_replace_content_pattern:
            (find, replace) = find_replace_content_pattern.split('|', 1)
            config = re.sub(find, replace, config)

        if update_jobs:
            # save modified config to new file
            file2 = workdir + '/' + job + '.xml.updated'
            fh = open(file2, 'w')
            fh.write(config)
            fh.close()
            if not quiet:
                os.system('diff {} {}'.format(file, file2))
            print("Updating job {}".format(job))
            if dryrun:
                print("Dryrun mode - job won't be updated")
            else:
                server_src.reconfig_job(job, config)

        if rename_jobs:
            (find, replace) = find_replace_jobname_pattern.split('|', 1)
            job2 = re.sub(find, replace, job)
            print('Renaming job {} => {}'.format(job, job2))
            if dryrun:
                print("Dryrun mode - job won't be renamed")
            else:
                server_dest.rename_job(job, job2)

        if clone_jobs:
            if from_template:
                (junk, job) = job.split('-', 1)
                # get rid of any reference to project type from config
                config = re.sub(tname + '-', '', config)
            if find_replace_jobname_pattern:
                (find, replace) = find_replace_jobname_pattern.split('|', 1)
                job = re.sub(find, replace, job)
            # cloning job has different name
            job = substitute_vars(job, properties)
            # save modified config to new file with different job name
            file2 = workdir + '/' + job + '.xml'
            fh = open(file2, 'w')
            fh.write(config)
            fh.close()
            if not quiet:
                os.system('diff {} {}'.format(file, file2))
            # check existence of job, create new or update existing job
            if server_dest.job_exists(job):
                print("Updating existing job {}job/{}".format(server_dest_url, job))
                if dryrun:
                    print("Dryrun mode - job won't be updated")
                else:
                    job_is_disabled = is_job_disabled(job, job_list)
                    server_dest.reconfig_job(job, config)
                    # leave state of build the same as it was before update
                    if job_is_disabled:
                        server_dest.disable_job(job)
                    else:
                        server_dest.enable_job(job)

            else:
                print("Creating new job {}job/{}".format(server_dest_url, job))
                if dryrun:
                    print("Dryrun mode - job won't be created")
                else:
                    server_dest.create_job(job, config)


if __name__ == "__main__":
    main()
