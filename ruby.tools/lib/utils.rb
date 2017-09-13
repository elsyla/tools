#!/usr/bin/env ruby

# standard libs
require 'yaml'
require 'systemu'

# global settings
$debug = false
$verbose = false
$dryrun = false

# common utilities and functions

def parse_job_name
  jobname = ENV["JOB_NAME"]
  if (jobname.nil?)
    puts "ERROR: JOB_NAME is not defined in the environment"
    exit 1
  end

  # parse jenkins jobname as build arguments
  # there are two possible formats
  # 1. jobname without release version: diycd-demo_app-deploy-dev-1
  # 2. jobname with release version: diycd-demo_app-1.0-deploy-dev-1
  release = nil
  jargs = jobname.split(/-/)
  domain = jargs.shift
  project = jargs.shift
  release = jargs.shift if jargs.first.match(/^\d+\.\d+/)
  task = jargs.shift
  param = jargs.join('-')
  if (release.nil?)
    release = '1.0' 
    puts "Jobname has no release info - setting RELEASE to #{release}"
  end
  namespace = "#{project}-#{release}"
  
  # global settings to be set later depending on job type
  env = nil

  if ($verbose)
    puts "domain = #{$domain}"
    puts "project = #{project}"
    puts "release = #{release}"
    puts "namespace = #{namespace}"
    puts "task = #{task}"
    puts "param = #{param}" if not param.nil?
  end

  # check naming conventions for deploy and test jobs
  if (task.match('deploy|test'))
    if (param !~ /^(dev|int|stg|prod)-(.+)$/)
      raise "FATAL: '#{task}' jobname missing env param"
    end
    env = param
  end

  return [domain,project,release,task,env]
end

def load_project_config(domain,project,release)
  central_path = "/data/central/projects/#{domain}/#{project}-#{release}"
  config = 'config.yml'
  config = "#{central_path}/meta/#{config}" if not File.exist?(config)
  puts "Loading project config #{config} ..."
  raise "FATAL: Missing project config #{config}" if not File.exist?(config)
  cfg = YAML.load_file(config)
  raise "FATAL: Unable to load project config #{$config}" if cfg.nil?
  puts cfg if $verbose
  prelease = get_build_token(cfg,'RELEASE').to_s
  if (release != prelease)
    puts prelease.class
    puts release.class
    puts "ERROR: Release version mismatch - jobname has #{release}, config has #{prelease}"
    exit 1
  end
  return cfg
end

def create_project
  # find project type from project config
  (domain,project,release,task,env) = parse_job_name()
  cfg = load_project_config(domain,project,release)
  # load all parts of jobname into main config for good use
  load_build_token(cfg,{'TASK'=>task})
  load_build_token(cfg,{'ENVIRONMENT'=>env})
  type = get_project_type(cfg)
  if (type =~ /maven_jar_app/)
    obj = MavenJar.new(cfg)
  else
    obj = Project.new(cfg)
  end
  # instantiate project from project type
  return obj
end

def get_build_token(cfg,token)
  tokens = get_hash_value(cfg,'build_tokens')
  raise "FATAL: Missing token '#{token}'" if tokens[token].nil?
  return tokens[token]
end

def get_env_variables(envhash)
  return get_hash_value(envhash,'env_variables')
end

def load_build_token(cfg,hash)
  cfg['build_tokens'].merge!(hash)
  puts cfg['build_tokens'] if $verbose
end

def get_project_envs(cfg)
  return get_hash_value(cfg,'envs')
end

def get_project_env_info(cfg,env,info)
  envs = get_hash_value(cfg,'envs')
  envs.each do |entry|
    if (entry['name'] == env)
      return get_hash_value(entry,info)
    end
  end
end

def get_project_domain(cfg)
  return get_build_token(cfg,'DOMAIN')
end

def get_project_name(cfg)
  return get_build_token(cfg,'PROJECT')
end

def get_project_type(cfg)
  return get_build_token(cfg,'PROJECT_TYPE')
end

def get_hash_value(cfg,key)
  val = cfg["#{key}"] 
  raise "FATAL: Hash key '#{key}' missing" if val.nil?
  return val
end

def get_deploy_tag(cfg,env)
  get_project_envs(cfg).each do |entry|
    return entry['deploy_tag'] if entry['name'] == env
  end
  raise "FATAL: Missing 'deploy_tag' tag"
end

def get_env_packages(env)
  return get_hash_value(env,'packages')
end

def get_env_package(env,pkg)
  get_env_packages(env).each do |entry|
    return entry[pkg] if not entry[pkg].nil?
  end
  raise "FATAL: Missing '#{pkg}' package"
end

def run_cmd(cmd)
  # run a command, return its output
  # raise fatal error if failed
  puts "CMD: #{cmd}"
  out = `#{cmd}`
  puts out if not out.empty?
  raise "FATAL: Failed to execute command" if not $?.success?
  return out
end

def run_cmd_seq(cmdseq)
  # run a sequence of commands, return the last command's output
  out = nil
  cmdseq.each do |cmd|
    out = run_cmd(cmd)
  end
  return out
end

def get_git_branch
  cmd = 'git status | head -n 1'
  out = run_cmd(cmd)
  if (out =~ /^On branch (.+)$/)
    return $1
  else
    raise "FATAL: Unrecognizable output from #{cmd}"
  end
end

def get_last_package_build_number(cfg)
  puts "Getting Maven package build number ..."
  release = get_build_token(cfg,'RELEASE')
  mgid = get_build_token(cfg,'MAVEN_GROUP_ID')
  maid = get_build_token(cfg,'MAVEN_ARTIFACT_ID')
  bno = -1
  # replace . with /  
  mgid = mgid.gsub('.', '/') 
  pkgloc = "~/.m2/repository/#{mgid}/#{maid}"
  status,out,err = systemu "ls #{pkgloc}"
  # if brand new package, last build number = -1
  return bno if not status.success?
  vers = out.split("\n").sort
  vers.each do |entry|
    next if not entry.match(/^#{release}\.\d+$/)
    tno = entry.split('.').last.to_i
    bno = tno if tno > bno
  end
  if (bno == -1)
    # show "none" rather than confusing -1 value
    puts "Last package build number = none"
  else
    puts "Last package build number = #{bno}"
  end
  return bno
end

def get_next_package_build_number(cfg)
  bno = get_last_package_build_number(cfg)
  bno = bno + 1
  puts "Next package build number = #{bno}"
  return bno
end

def retry_cmd(cmdhash)
  # run a command, return its output
  # retry if error depending on parameters as hash keys
  # cmd: the command to be executed
  # retry_no: the number of retries
  # rescue_regex: the error pattern to be rescued for repeating loop
  # break_regex: the error pattern to break out of loop as okay
  cmd = cmdhash['cmd']
  retries = cmdhash['retries']
  secs = cmdhash['sleep_secs']
  rescueregex = cmdhash['rescue_regex']
  breakregex = cmdhash['break_regex']
  for i in 0..retries
    puts "CMD(#{i}): #{cmd}"
    status,stdout,stderr = systemu cmd
    if (status.success?)
      puts stdout if not stdout.empty?
      return stdout
    end
    stderr = stdout if stderr.empty?
    raise "FATAL: Exception has no output" if stderr.empty?
    puts stderr 
    if (not breakregex.nil?)
      return if stderr.match(/#{breakregex}/)
    end
    if (not rescueregex.nil?)
      if (stderr.match(/#{rescueregex}/))
        puts "Exception is rescued - sleeping #{secs} secs before retrying ..."
        sleep secs
        next 
      else
        raise "FATAL: Unable to rescue exception"
      end
    end
  end
end

def check_in_source_location(cloc,rloc)
  # cloc = central location, rloc = relative location
  rescueregex = '(Unable to create|failed to lock|cannot lock HEAD ref)'
  breakregex = 'nothing to commit'
  # get true relative location by getting rid of "root" path
  rloc = rloc.gsub(/#{cloc}\//,'')
  out = retry_cmd({ 'cmd'=>"cd #{cloc} && git add #{rloc}",
                    'retries'=>6,
                    'sleep_secs'=>5,
                    'rescue_regex'=>rescueregex})
  out = retry_cmd({ 'cmd'=>"cd #{cloc} && git commit -m 'auto update #{rloc}'",
                    'retries'=>6,
                    'sleep_secs'=>5,
                    'rescue_regex'=>rescueregex,
                    'break_regex'=>breakregex})
  return out if out =~ /breakregex/
  return retry_cmd({ 'cmd'=>"cd #{cloc} && git push origin master",
                     'retries'=>6,
                     'sleep_secs'=>5,
                     'rescue_regex'=>rescueregex})
end

def substitute_file(fname, tokens)
  puts "Substituting file #{fname} ..."

  result = []
  next_line = nil
  if (not fname.nil?)
    raise "FATAL: File #{fname} does not exist" unless File.exist?(fname)
    ofile = File.open(fname, "r")
    next_line = nil
    ofile.each do |line|
      # if next line is set, save it (set substituted line as the next line)
      if (not next_line.nil?)
        result.push(next_line)
        next_line = nil
        next
      end
      # have to put quotes around 'line' to avoid changing 'original' 
      # weird perl/ruby behavior
      original = "#{line}"
      modified = false
      #puts "Processing line: #{line}"
      tokens.keys.each do |key|
        val = tokens["#{key}"]
        if (line.match(/\[#{key}\]/))
          modified = true
          line.gsub!("[#{key}]", "#{val}")
        end
      end
      # look for comment line starting with '<--' for xml and '#' for any other
      # pattern must be exact. no exception.
      if (modified && line =~ /^\s*(#|<!--)/)
        result.push(original)
        # remember to replace next line with substituted line
        next_line = line.gsub(/^#/,'').gsub(/<!--/,'').gsub(/-->$/,'') 
      else
        result.push(line)
      end
      if (modified) 
        puts "Original line   : #{original}"
        puts "Substituted line: #{line}"
      end
    end
    ofile.close

    f = File.new(fname, "w")
    result.each do |line|
      f.write(line) 
    end
    f.close 
  end
end
