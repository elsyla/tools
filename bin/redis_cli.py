#! /usr/bin/env python3
# https://redis-py.readthedocs.io/en/latest/

import time
import os
import argparse
import redis
import socket
import ast
import yaml
import subprocess
import datetime
import json
import re

# global vars
thishost = socket.gethostname()
SIH = None
SAH = None
DEBUG = False
QUIET = False


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--quiet', help='reduce verbosity', action='store_true')
    parser.add_argument('--debug', help='debugging output', action='store_true')
    parser.add_argument('--redis_server', help='redis server')
    parser.add_argument('--redis_port', help='redis port')
    parser.add_argument('--redis_passphrase', help='redis passphrase')
    parser.add_argument('--service', help='service in context')
    parser.add_argument('--toggle_svc_status', help='toggle service status between active and inactive',
                        action='store_true')
    parser.add_argument('--list_inventory', help='list inventory of service', action='store_true')
    parser.add_argument('--refresh_inventory', help='refresh inventory with default inventory file', action='store_true')
    parser.add_argument('--show_all_servers', help='show all servers in all services', action='store_true')
    parser.add_argument('--default_inventory_file', help='default inventory file to update redis')
    parser.add_argument('--bg_state', help='use with --list_inventory to filter state (blue, green, or all) of servers')
    parser.add_argument('--svc_status',
                        help='use with --list_inventory to filter service status (active or inactive) of servers')
    parser.add_argument('--switch_bg_state', help='switch blue green state', action='store_true')
    args = parser.parse_args()
    if args.debug:
        global DEBUG
        DEBUG = True
    if args.debug:
        global QUIET
        QUIET = True
    service = args.service
    if service:
        global SIH
        SIH = service + '_info_hash'
        global SAH
        SAH = service + '_action_hash'
    if args.switch_bg_state or args.list_inventory or args.toggle_svc_status:
        if not service:
            print('error: switch blue green requires --service')
            exit(1)
    elif not (args.list_inventory or args.refresh_inventory or args.show_all_servers):
        print("error: --list_inventory, --refresh_inventory or --show_all_servers is required")
        exit(1)
    if args.refresh_inventory and not args.default_inventory_file:
        print("error: --refresh_inventory and --default_inventory_file must both be specified")
        exit(1)
    return args


def create_redis_server_instance(rs):
    rp = 6379
    rpw = ''
    if DEBUG:
        print("creating redis server instance {}".format(rs))
    rsi = redis.StrictRedis(host=rs, port=rp, db=0, password=rpw)
    if not rsi:
        print("error: unable to create redis server instance")
        exit(1)
    return rsi


def get_default_inventory(service, invfile):
    if not os.path.exists(invfile):
        inv = service + '/' + invfile
        if not os.path.exists(invfile):
            print('error: {} file does not exist'.format(invfile))
            exit(1)
    proc = subprocess.Popen(invfile, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (out, err) = proc.communicate()
    if out:
        out = str(out, 'utf-8').rstrip('\n')
    if err:
        err = str(err, 'utf-8').rstrip('\n')
        print(err)
        exit(1)
    data = json.loads(out)
    return data


def create_redis_server_instances():
    servers = ['pit-redis.prod.wc1.yellowpages.com', 'pit-redis.np.wc1.yellowpages.com']
    service = 'redis-service'
    found = False
    arsi = None
    irsi = None
    for server in servers:
        try:
            rsi = create_redis_server_instance(server)
            status = get_server_svc_status(rsi, service, server)
        except:
            continue
        if status == 'active':
            arsi = rsi
            found = True
        elif status == 'inactive':
            irsi = rsi
    if not found:
        print('error: no active redis server found')
        exit(1)
    return arsi, irsi


def get_server_bg_state(rsi, service, server):
    state = None
    ci = rsi.get(service)
    if not ci:
        print('error: service {} is unavailable or in bad state'.format(service))
        exit(1)
    ci = convert_bytes_string(ci)
    data = ci.get('_meta').get('hostvars').get(server).get('bg_state')
    if data:
        state = data
    return state


def get_server_svc_status(rsi, service, server):
    status = None
    ci = rsi.get(service)
    if not ci:
        if service == 'redis-service':
            print('warning: {} is missing data for {} so its status is set as inactive.'.format(server, service))
            return 'inactive'
        else:
            print('error: service {} is unavailable or in bad state'.format(service))
            exit(1)
    ci = convert_bytes_string(ci)
    data = ci.get('_meta').get('hostvars').get(server).get('svc_status')
    if data:
        status = data
    return status


def run_cmd(cmd):
    timestamp = '{:%Y-%m-%d %H:%M:%S}'.format(datetime.datetime.now())
    print("%s: %s" % (timestamp, cmd))
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (out, err) = proc.communicate()
    if out:
        out = str(out, 'utf-8').rstrip('\n')
        print(out)
    if err:
        err = str(err, 'utf-8').rstript('\n')
        print(err)
    return proc.returncode


def get_stored_inventory(rsi, service, filter):
    inventory = rsi.get(service)
    if not inventory:
        print('error: {} has no inventory'.format(service))
        exit(1)
    inventory = convert_bytes_string(rsi.get(service))
    hostvars = inventory.get('_meta').get('hostvars')
    servers = []
    for server in hostvars.keys():
        if filter == 'all':
            servers.append(server)
        elif hostvars.get(server).get('bg_state') == filter:
            servers.append(server)
        elif hostvars.get(server).get('svc_status') == filter:
            servers.append(server)
    # clone inventory
    temp_inventory = dict(inventory)
    for hkey in temp_inventory.keys():
        active_hkey = []
        inactive_hkey = []
        if hkey == '_meta':
            continue
        allservers = temp_inventory[hkey]['hosts']
        filtered_servers = []
        if not allservers:
            continue
        for server in allservers:
            status = temp_inventory.get('_meta').get('hostvars').get(server).get('svc_status')
            if status == 'active':
                active_hkey.append(server)
            elif status == 'inactive':
                inactive_hkey.append(server)
            else:
                print('error: {} has unknown service status'.format(server))
                exit(1)
            if server in servers:
                filtered_servers.append(server)
        inventory['active_' + hkey] = {'hosts': active_hkey}
        inventory['inactive_' + hkey] = {'hosts': inactive_hkey}
        inventory[hkey]['hosts'] = filtered_servers
    return inventory


def get_updated_inventory(rsi, service, filter, invfile):
    inventory = rsi.get(service)
    new_inventory = get_default_inventory(service, invfile)
    new_hostvars = new_inventory.get('_meta').get('hostvars')
    if not new_hostvars:
        print('fatal: missing meta hostvars definition in default inventory')
        exit(1)
    if inventory:
        inventory = convert_bytes_string(rsi.get(service))
        hostvars = inventory.get('_meta').get('hostvars')
        for server in new_hostvars.keys():
            if hostvars.get(server):
                # load current blue green state of server into new inventory
                new_hostvars[server]['bg_state'] = hostvars[server]['bg_state']
                # load current active inactive status of server into new inventory
                new_hostvars[server]['svc_status'] = hostvars[server]['svc_status']
        new_inventory['_meta']['hostvars'] = new_hostvars
    rsi.set(service, new_inventory)
    new_hostvars = new_inventory.get('_meta').get('hostvars')
    servers = []
    for server in new_hostvars.keys():
        if filter == 'all':
            servers.append(server)
        elif new_hostvars.get(server).get('bg_state') == filter:
            servers.append(server)
        elif new_hostvars.get(server).get('svc_status') == filter:
            servers.append(server)
    temp_inventory = dict(new_inventory)
    for hkey in temp_inventory.keys():
        active_hkey = []
        inactive_hkey = []
        if hkey == '_meta':
            continue
        allservers = temp_inventory[hkey]['hosts']
        filtered_servers = []
        if not allservers:
            continue
        for server in allservers:
            status = temp_inventory.get('_meta').get('hostvars').get(server).get('svc_status')
            if status == 'active':
                active_hkey.append(server)
            elif status == 'inactive':
                inactive_hkey.append(server)
            else:
                print('error: {} has unknown service status'.format(server))
                exit(1)
            if server in servers:
                filtered_servers.append(server)
        new_inventory['active_' + hkey] = {'hosts': active_hkey}
        new_inventory['inactive_' + hkey] = {'hosts': inactive_hkey}
        new_inventory[hkey]['hosts'] = filtered_servers
    return new_inventory


def switch_bg_state(rsi, service, brsi=None):
    print("switching blue green state of {}".format(service))
    inventory = rsi.get(service)
    if not inventory:
        print('error: inventory undefined in redis for {}'.format(service))
        exit(1)
    inventory = convert_bytes_string(inventory)
    hostvars = inventory.get('_meta').get('hostvars')
    for server in hostvars.keys():
        if hostvars.get(server).get('bg_state') == 'blue':
            print('switching {} from blue to green'.format(server))
            hostvars[server]['bg_state'] = 'green'
        elif hostvars.get(server).get('bg_state') == 'green':
            print('switching {} from green to blue'.format(server))
            hostvars[server]['bg_state'] = 'blue'
        else:
            print('warning: {} has no blue/green state'.format(server))
    inventory['_meta']['hostvars'] = hostvars
    rsi.set(service, inventory)
    if brsi:
        brsi.set(service, inventory)
    return True


def toggle_svc_status(rsi, service, brsi=None):
    print("toggling service status of {}".format(service))
    inventory = rsi.get(service)
    if not inventory:
        print('error: inventory undefined in redis for {}'.format(service))
        exit(1)
    inventory = convert_bytes_string(inventory)
    hostvars = inventory.get('_meta').get('hostvars')
    for server in hostvars.keys():
        if hostvars.get(server).get('svc_status') == 'active':
            print('toggling {} from active to inactive'.format(server))
            hostvars[server]['svc_status'] = 'inactive'
        elif hostvars.get(server).get('svc_status') == 'inactive':
            print('toggling {} from inactive to active'.format(server))
            hostvars[server]['svc_status'] = 'active'
        else:
            print('warning: {} has no service status'.format(server))
    inventory['_meta']['hostvars'] = hostvars
    rsi.set(service, inventory)
    if brsi:
        if service == 'redis-service':
            # update inactive database with active database for all services
            for svc_key in rsi.keys('*-service'):
                svc_key = svc_key.decode("utf-8")
                val = rsi.get(svc_key)
                brsi.set(svc_key, val)
        else:
            brsi.set(service, inventory)
    return True


def get_blue_servers(rsi, service):
    inventory = convert_bytes_string(rsi.get(service))
    hostvars = inventory.get('_meta').get('hostvars')
    servers = []
    for server in hostvars.keys():
        if hostvars.get(server).get('bg_state') == 'blue':
            servers.append(server)
    for service in inventory.keys():
        if service == '_meta':
            continue
        inventory[service]['hosts'] = servers
    return inventory


def list_inventory(rsi, service, filter, invfile=None):
    if invfile:
        inventory = get_updated_inventory(rsi, service, filter, invfile)
    else:
        inventory = get_stored_inventory(rsi, service, filter)
    # save a copy of the inventory for ansible to use
    ifile = '/var/tmp/' + service + '.inventory'
    fh = open(ifile, 'w')
    fh.write(json.dumps(inventory, sort_keys=True, indent=2))
    fh.close()
    print(json.dumps(inventory, sort_keys=True, indent=2))
    return True


def refresh_inventory(rsi, service, invfile):
    new_inventory = get_default_inventory(service, invfile)
    rsi.set(service, new_inventory)
    return True


def show_all_servers(rsi):
    services = rsi.keys('*-service')
    for service in services:
        service = service.decode()
        print(service)
        inventory = convert_bytes_string(rsi.get(service))
        for role in inventory.keys():
            if role == '_meta':
                continue
            # print(json.dumps(inventory, sort_keys=True, indent=2))
            print('- {}'.format(role))
            for server in inventory[role]['hosts']:
                data = inventory.get('_meta').get('hostvars').get(server)
                print('  - {} {}'.format(server, data))

    return True


def get_server_list(si, service, state):
    servers = []
    allservers = si.hkeys(SIH)
    for server in allservers:
        if state == 'all':
            servers.append(server)
        elif get_current_server_state(si, server) == state:
            servers.append(server)
    if not servers:
        print("warning: {} service has no server in {} state".format(service, state))
    return servers


def get_current_server_state(si, server):
    # first get current server state in redis
    attributes = si.hget(SIH, server)
    if attributes:
        attributes = convert_bytes_string(attributes)
        if attributes['bg_state']:
            return attributes['bg_state']
    return None


def set_current_server_state(si, server, state):
    attributes = si.hget(SIH, server)
    if attributes:
        attributes = convert_bytes_string(attributes)
        attributes['bg_state'] = state
    else:
        attributes = {'bg_state': state}
    si.hset(SIH, server, attributes)
    return True


def convert_bytes_string(bytes_str):
    data = ast.literal_eval(bytes_str.decode())
    return data


def main():
    args = parse_args()

    if args.redis_server:
        rsi = create_redis_server_instance(args.redis_server)
    else:
        (rsi, brsi) = create_redis_server_instances()

    if args.show_all_servers:
        show_all_servers(rsi)
        exit(0)

    service = args.service
    # auto append specified service with '-service' for clear separation in redis
    if not re.match(service + '-service', service):
        service = service + '-service'

    if args.list_inventory:
        filter = 'all'
        if args.bg_state:
            filter = args.bg_state
        if args.svc_status:
            filter = args.svc_status
        list_inventory(rsi, service, filter, args.default_inventory_file)

    if args.refresh_inventory:
        refresh_inventory(rsi, service, args.default_inventory_file)
        list_inventory(rsi, service, 'all', args.default_inventory_file)

    if args.toggle_svc_status:
        if service == 'redis-service' and brsi == None:
            print('error: cannot toggle redis service status without both active and inactive servers')
            exit(1)
        toggle_svc_status(rsi, service, brsi)

    if args.switch_bg_state:
        switch_bg_state(rsi, service, brsi)


if __name__ == "__main__":
    main()
    exit(0)
