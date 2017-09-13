#!/usr/bin/env ruby

# standard libs
require 'yaml'
require 'fileutils'

# diycd libs
require 'utils'

class Project
  
  def initialize(cfg)
    @@config = cfg
    @@domain = get_build_token(cfg,'DOMAIN')
    @@project = get_build_token(cfg,'PROJECT')
    @@release = get_build_token(cfg,'RELEASE')
    @@task = get_build_token(cfg,'TASK')
    @@env = nil
    # if task is deploy or test, there must be provided env
    @@env = get_build_token(cfg,'ENVIRONMENT') if @@task =~ /^(deploy|test)$/
    @@namespace = "#{@@project}-#{@@release}"
    @@gitbranch = get_git_branch() if @@task =~ /^(build|devbuild|assemble)$/
    if (not @env.nil?)
      (@@stage, @@partition) = @@env.split('-')
    else
      @@stage = @@partition = nil
    end
    @@centralpath = '/data/central/projects'
    @@centralenvs = "#{@@centralpath}/#{@@domain}/#{@@namespace}/envs"
    @@centraltags = "#{@@centralpath}/#{@@domain}/#{@@namespace}/tags"
    @@centralmeta = "#{@@centralpath}/#{@@domain}/#{@@namespace}/meta"
    @@centralconfig = "#{@@centralmeta}/config.yml"
    @@centralrelhist = "#{@@centralmeta}/relhist.yml"
  end
  
  def deploy_env(taskdef)
    puts "Deploying env #{@@env} ..."
    run_cmd_seq(taskdef['cmd_seq'])
    update_task_tag()
  end
  
  def test_env(taskdef)
    puts "Testing env #{@@env} ..."
    run_cmd_seq(taskdef['cmd_seq'])
    update_task_tag()
  end
  
  def assemble_project(taskdef)
    puts "Assembling project #{@@project} ..."

    pkgbno = get_last_package_build_number(@@config)
    pkgver = "#{@@release}.#{pkgbno}"
    load_build_token(@@config,{"PACKAGE_VERSION"=>pkgver})
    update_project_tokens()
    update_project_envs()
    update_release_version()
    update_task_tag()
  end
  
  def build_project(taskdef)
    puts "Building project #{@@project} ..."
    update_central_project_config()
    pkgbno = get_next_package_build_number(@@config)
    pkgver = "#{@@release}.#{pkgbno}"
    load_build_token(@@config,{"PACKAGE_VERSION"=>pkgver})
    update_project_tokens()
    run_cmd_seq(taskdef['cmd_seq'])
    update_task_tag()
  end
  
  def devbuild_project(taskdef)
    puts "Building project #{@@project} on '#{@@gitbranch}' ..."
    # for dev build, use jenkins job's build number
    pkgbno = ENV['BUILD_NUMBER']
    pkgver = "#{@@release}.#{pkgbno}"
    load_build_token(@@config,{"PACKAGE_VERSION"=>pkgver})
    update_project_tokens()
    run_cmd_seq(taskdef['cmd_seq'])
  end
  
  def run
    puts @@config
    if (@@task == 'build')
        self.build_project()
    elsif (@@task == 'devbuild')
      self.devbuild_project()
    elsif (@@task == 'assemble')
      self.assemble_project()
    elsif (@@task == 'deploy')
      self.deploy_env()
    elsif (@@task == 'test')
      self.test_env()
    end
    exit 0
  end

  def update_project_envs
    puts "Updating environments ..."
    if (not File.exist?(@@centralenvs))
      FileUtils.mkdir_p(@@centralenvs)
    end
    relver = get_next_release_version()
    gitrev = run_cmd("git rev-parse HEAD").chomp
    envfiles = Dir.glob("envs/*.yml")
    # iterate through all envs
    envfiles.each do |envfile|
      envhash = YAML.load_file(envfile)
      raise "FATAL: Unable to load env" if envhash.nil?
      # add next release version to env state
      envhash['release_version'] = relver
      envhash['git_revision'] = gitrev
      # compare env between project repo and central repo
      envname = envfile.gsub('envs/','').gsub('.yml','')
      envdir = "#{@@centralenvs}/#{envname}"
      statefile = "#{envdir}/state.yml"
      # if central env folder doesn't exist, create it
      if (not File.exist?(envdir))
        FileUtils.mkdir_p(envdir)
      end
      file = File.open(statefile, "w")
      file.write(envhash.to_yaml)
      file.close
    end
    return check_in_source_location(@@centralpath,@@centralenvs)
  end

  def update_task_tag
    tag = nil
    taghash = nil

    #  tag = get_tag()
    if (@@task.match('build'))
      tag = 'LAST_BUILT'
      taghash = { "packages" => ["name" => get_build_token(@@config,'MAVEN_ARTIFACT_ID'), "version" => get_build_token(@@config,'PACKAGE_VERSION')] }
    elsif (@@task.match('assemble'))
      tag = 'LAST_ASSEMBLED'
      taghash = { "release_version" => get_build_token(@@config,'RELEASE_VERSION'), "git_revision" => get_build_token(@@config,'GIT_REVISION') }
    elsif (@@task.match('deploy'))
      (stage, partition) = @@env.upcase.split('-')
      tag = 'LAST_DEPLOYED_' + stage + "-#{partition}"
      taghash = { "release_version" => get_build_token(@@config,'RELEASE_VERSION'), "git_revision" => get_build_token(@@config,'GIT_REVISION') }
    elsif (@@task.match('test'))
      (stage, partition) = @@env.upcase.split('-')
      tag = 'LAST_TESTED_' + stage + "-#{partition}"
      taghash = { "release_version" => get_build_token(@@config,'RELEASE_VERSION'), "git_revision" => get_build_token(@@config,'GIT_REVISION') }
    end
    
    puts "Updating tag #{tag} ..."
    puts taghash

    if (not File.exist?(@@centraltags))
      FileUtils.mkdir_p(@@centraltags)
    end

    tagfile = "#{@@centraltags}/#{tag}.yml"
    file = File.open(tagfile, "w")
    file.write(taghash.to_yaml)
    file.close
    
    check_in_source_location(@@centralpath,@@centraltags)
  end

  def update_central_project_config
    puts "Updating central project config ..."
    if (not File.exist?(@@centralmeta))
      FileUtils.mkdir_p(@@centralmeta)
    end
    # compare config between project repo and central repo
    do_update = false
    lcfg = 'config.yml'
    if (not File.exist?(@@centralconfig))
      do_update = true
    else
      ok = system "diff #{lcfg} #{@@centralconfig}"
      do_update = true if not ok
    end

    if (do_update)
      system "cp -fp  #{lcfg} #{@@centralmeta}" 
      return check_in_source_location(@@centralpath,@@centralmeta)
    end
  end

  def update_release_version
    puts "Creating release version ..."
    # load release history from central location
    relhash = Hash.new
    if (File.exist?(@@centralrelhist))
      relhash = YAML.load_file(@@centralrelhist) 
    else
      if (not File.exist?(@@centralmeta))
        FileUtils.mkdir_p(@@centralmeta)
      end
    end
    rev = run_cmd("cd #{@@centralpath} && git rev-parse HEAD").chomp
    # starting version
    ver = "#{@@release}.0"
    if (not relhash.empty?)
      nextno = relhash.keys.last.split(/\./).last.to_i + 1
      ver = "#{@@release}.#{nextno}"
    end
    
    relhash["#{ver}"] = rev
    puts "New release version = #{ver}"
    # set useful tokens in global config
    load_build_token(@@config,{'RELEASE_VERSION'=>ver})
    load_build_token(@@config,{'GIT_REVISION'=>rev})
    file = File.open(@@centralrelhist, "w")
    file.write(relhash.to_yaml)
    file.close
    return check_in_source_location(@@centralpath,@@centralmeta)
  end

  def get_next_release_version
    puts "Getting next release version ..."
    # starting version
    # load release history from central location
    ver = "#{@@release}.0"
    relhash = Hash.new
    if (File.exist?(@@centralrelhist))
      relhash = YAML.load_file(@@centralrelhist) 
      if (not relhash.empty?)
        nextno = relhash.keys.last.split(/\./).last.to_i + 1
        ver = "#{@@release}.#{nextno}"
      end
    end
    puts "Next release version = #{ver}"
    return ver
  end

  def update_project_tokens
    # get build tokens
    tokens = get_hash_value(@@config,'build_tokens')

    # do substitutions for tokens and env vars in specified files
    puts "Substituting files ..."
    get_hash_value(@@config,'substitute_files').each do |sfile|
      fname = sfile['name']
      pattern = sfile['pattern']
      envvars = sfile['env_tokens']
      allvars = tokens

      if (not envvars.nil?)
        envvars.each do |var|
          allvars["#{var}"] = ENV["#{var}"] unless ENV["#{var}"].nil?
        end
      end

      substitute_file(fname, allvars) if not fname.nil?

      if (not pattern.nil?)
        path = '.'
        glob = pattern
        if (pattern.match(/.+\/.*/))
          (path, glob) = pattern.split('/')
        end
        files = `find #{path} -name "#{glob}"`.split("\n")
        files.each do |fname|
          substitute_file(fname, allvars)
        end
      end
    end
  end

  # end Project class
end
