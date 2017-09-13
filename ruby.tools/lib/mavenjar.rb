#!/usr/bin/env ruby

# standard libs
require 'yaml'
require 'fileutils'

# diycd libs
require 'utils'
require 'project'

class MavenJar < Project

  def initialize(cfg)
    super
    @@task = get_build_token(cfg,'TASK')
    if (@@task == 'devbuild')
      # if task = devbuild, then add _dev to package name
      maid = get_build_token(@@config,'MAVEN_ARTIFACT_ID')
      load_build_token(@@config,{'MAVEN_ARTIFACT_ID'=>"#{maid}_dev"})
    end
    @@maid = get_build_token(@@config,'MAVEN_ARTIFACT_ID')
    @@mgid = get_build_token(@@config,'MAVEN_GROUP_ID')
    @@deploypath = "/data/envs/#{@@domain}/#{@@namespace}"
    @@mavenrepo = ENV['HOME'] + '/.m2'
  end

  def build_project()
    taskdef = Hash.new
    taskdef['cmd_seq'] = ["mvn clean install"]
    super(taskdef)
  end

  def devbuild_project()
    taskdef = Hash.new
    taskdef['cmd_seq'] = ["mvn clean package"]
    super(taskdef)
    deployjar = "#{@@maid}.jar"
    testscript = "scripts/launch_test.rb"
    # iterate through dev-* env(s)
    get_project_envs(@@config).each do |entry|
      env = entry['name']
      next if env.nil? || env !~ /^dev-.+$/
      deployenv = "#{@@deploypath}/#{env}"
      # now do addition dev build steps for maven jar app
      pkgver = get_build_token(@@config,'PACKAGE_VERSION')
      devpkg="#{@@maid}-#{pkgver}.jar"
      run_cmd("cp target/#{devpkg} #{deployenv}/#{devpkg}")
      run_cmd("cd #{deployenv} && ln -sf #{devpkg} #{deployjar}")
      run_cmd("cd #{deployenv} && jar xvf #{deployjar} #{testscript}")
      run_cmd("cd #{deployenv} && ruby #{testscript}")
    end
  end

  def assemble_project()
    taskdef = Hash.new
    taskdef['cmd_seq'] = ['echo hello world']
    super(taskdef)
  end

  def deploy_env()
    deployenv = "#{@@deploypath}/#{@@env}"
    deployjar = "#{@@maid}.jar"
    testscript = "scripts/launch_test.rb"

    tag = get_deploy_tag(@@config,@@env)
    puts "Deploy tag = #{tag}"
    relpath = "#{@@domain}/#{@@namespace}"
    tagfile = "#{@@centraltags}/#{tag}.yml"
    raise "FATAL: Missing tag #{tagfile} " if not File.exist?(tagfile)
    taghash = YAML.load_file(tagfile) 
    puts taghash
    relver = taghash['release_version']
    gitrev = taghash['git_revision']

    # load release_version into global config hash for other functions to use
    load_build_token(@@config,{'RELEASE_VERSION'=>relver})
    load_build_token(@@config,{'GIT_REVISION'=>gitrev})
    envstate = "#{relpath}/envs/#{@@env}/state.yml"
    # get state of env at particular release version/git rev
    out = run_cmd("cd #{@@centralpath} && git show #{gitrev}:#{envstate}")
    envhash = YAML.load(out)
    puts envhash
    # process main package for demo. other pkgs not being dealt with
    mainpkg = get_env_package(envhash,'main')
    pkgver = mainpkg.split('-').last
    artifact="#{@@mgid}:#{@@maid}:#{pkgver}"
    buildpkg="#{@@maid}-#{pkgver}.jar"
    # process env variables for demo
    arr = Array.new
    efile = 'env_variables'
    # refresh file holding env variables
    arr.push("cd #{deployenv} && rm -f #{efile}")
    # create entry to export env variables with say 'source' command
    vars = get_env_variables(envhash)
    vars.keys.each do |key|
      val = get_hash_value(vars,key)
      arr.push("cd #{deployenv} && echo 'export #{key}=\"#{val}\"' >> #{efile}")
    end
    taskdef = Hash.new
    taskdef['cmd_seq'] = [
                          "mvn org.apache.maven.plugins:maven-dependency-plugin:LATEST:get -DremoteRepositories=#{@@mavenrepo} -Dartifact=#{artifact} -Ddest=#{deployenv}/#{buildpkg}",
                          "cd #{deployenv} && ln -sf #{buildpkg} #{deployjar}",
                          "cd #{deployenv} && jar xvf #{deployjar} #{testscript}",
                         ].concat(arr)
    super(taskdef)
  end

  def test_env()
    deployenv = "#{@@deploypath}/#{@@env}"
    tag = get_deploy_tag(@@config,@@env)
    puts "Deploy tag = #{tag}"
    relpath = "#{@@domain}/#{@@namespace}"
    tagfile = "#{@@centraltags}/#{tag}.yml"
    raise "FATAL: Missing tag #{tagfile} " if not File.exist?(tagfile)
    taghash = YAML.load_file(tagfile) 
    puts taghash
    relver = taghash['release_version']
    gitrev = taghash['git_revision']
    # load release_version into global config hash for other functions to use
    load_build_token(@@config,{'RELEASE_VERSION'=>relver})
    load_build_token(@@config,{'GIT_REVISION'=>gitrev})
    envstate = "#{relpath}/envs/#{@@env}/state.yml"
    # get state of env at particular release version/git rev
    out = run_cmd("cd #{@@centralpath} && git show #{gitrev}:#{envstate}")
    envhash = YAML.load(out)
    puts envhash
    testscript = "scripts/launch_test.rb"
    taskdef = Hash.new
    taskdef['cmd_seq'] = ["cd #{deployenv} && ruby #{testscript}"]
    super(taskdef)
  end
  
  # end MavenJar
end
