#!/usr/bin/env ruby

# load path of our libs
if (ENV['USER'] == 'jenkins')
  $:.unshift ('/data/central/tools/lib')
else
  #$:.unshift File.join( %w{ ./ lib } )
  $:.unshift ('~/diycd/tools/lib')
end

# global libs
require 'getoptlong'
require 'yaml'
require 'fileutils'

# diycd libs
require 'utils'
require 'project'
require 'mavenjar'

opts = GetoptLong.new(
                      [ '--help', '-h', GetoptLong::NO_ARGUMENT ],
                      [ '--debug', '-d', GetoptLong::NO_ARGUMENT ],
                      [ '--verbose', '-v', GetoptLong::NO_ARGUMENT ],
                      [ '--yamlofproject', '-y', GetoptLong::REQUIRED_ARGUMENT ],
                      [ '--locationofproject', '-l', GetoptLong::REQUIRED_ARGUMENT ],
                      [ '--jobregex', GetoptLong::REQUIRED_ARGUMENT ],
                      [ '--jenkinspipeline', GetoptLong::NO_ARGUMENT ],
                      [ '--gitstructure', GetoptLong::NO_ARGUMENT ],
                      [ '--rolesdbenvs', GetoptLong::NO_ARGUMENT ],
                      [ '--codecoverage', GetoptLong::NO_ARGUMENT ],
                      [ '--projectlist', GetoptLong::REQUIRED_ARGUMENT ],
                      )

def usage
  puts "USAGE: #{$0} <argument list>
--help, -h: show this help message
--debug, -d: run with more verbosity and side effects - additional debug logics
--verbose, -v: run with more verbosity with no side effect, unlike --debug mode
--yamlofproject projects/<system>-<subsystem.yaml>, -y: required
--locationofproject <location>, -l: required for --gitstructure and --rolesdbenvs
   git location of project to be audited
--gitstructure: optional
   audit git repo and structure including folders and files
--jenkinspipeline: optional
   audit jenkins pipeline and jobs matching <system>-<subsystem> or specified via --jobregex
--rolesdbenvs: optional
   audit environments as roles in rolesdb 
--codecoverage: optional
   check code coverage to meet minimum threshold
--jobregex <pattern>: optional for --jenkinspipeline
   regular expression for jobs. eg. urs-tumblr_features
   if not specified, it is formulated as <system>-<subsystem> per settings in project yaml
"
  exit 0
end

opts.each do |opt, arg|
  case opt
  when '--help'
    usage
  when '--debug'
    $verbose = $debug = true
  when '--verbose'
    $verbose = true
  when '--deploy'
    $deploy = true
  when '--test'
    $test = true
  end
end

project = create_project()
project.run()

exit 0
