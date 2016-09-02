# central tools collaborative automation framework

# binaries
bin/jcli.py - Jenkins Command-Line Interface
              swiss army knife for developers to manage (create, read, edit, delete) Jenkins jobs based on project template and property (config) file
bin/jmon.py - Jenkins Monitoring and Provisioning
              active adaptable monitoring and provisioning for Jenkins instance(s) from bring-up to operational

# libraries
lib/utils.py - top-level Command, Host and <subclass>Host, and Utils classes
lib/jmon_utils.py - second-level <subclass>Host and JenkinsMonitoring classes
lib/project.py - top-level generic Project class
lib/webapp.py - second-level Webapp class
