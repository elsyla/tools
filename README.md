# central tools and collaborative automation framework
#

# binaries
bin/jcli.py - Jenkins Command-Line Interface<br>
  swiss army knife for developers to manage (create, read, edit, delete) Jenkins jobs based on project template and property (config) file<br>
bin/jmon.py - Jenkins Monitoring and Provisioning<br>
  active adaptable monitoring and provisioning for Jenkins instance(s) from bring-up to operational<br>
bin/build.py - script performing build and release tasks 

# libraries
lib/utils.py - top-level common Command, Host, and Utils classes<br>
lib/jmon_utils.py - second-level Jenkins Host and Monitoring classes<br>
lib/project.py - top-level common Project class<br>
lib/webapp.py - second-level Webapp class<br>

# configs
config/template.properties - config file of template Webapp for cloning new and/or updating existing projects<br>
config/jmon.properties - config file of jenkins monitoring and provisioning utility job
