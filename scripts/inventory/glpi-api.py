#!/usr/bin/env python
# coding: utf-8

"""Ansible dynamic inventory for GLPI REST API."""

import os
import sys
import re
import copy
import argparse
import json
import yaml
import yamlloader
import requests
from glpi_api import GLPI, GLPIError

PY_VERSION = sys.version_info.major

# HTTP requests debugging (FIXME: add an option?)
#import logging
#requests_logger = logging.getLogger('urllib3')
#requests_handler = logging.StreamHandler()
#requests_handler.setFormatter(logging.Formatter())
#requests_logger.addHandler(requests_handler)
#requests_logger.setLevel('DEBUG')
##import http.client as http_client
##http_client.HTTPConnection.debuglevel = 1


# Configuration parameters of a group.
GROUP_PARAMS = ('itemtype',         # GLPI item type
                'criteria',         # GLPI search criteria
                'metacriteria',     # GLPI search metacriteria
                'fields',           # GLPI search forcedisplay
                'hostname',         # how to generate inventory_hostname value
                'vars',             # Ansible vars for the group
                'hostvars',         # Ansible hostvars attached to group hosts
                'children',         # Children of the group
                'retrieve')         # Force retrieval of data

class GLPIInventoryError(Exception):
    """Exception for this program (catched in `main`)."""
    pass

def main():
    """Main function.

    For preventing functions to have too many arguments and the boilerplate when
    passing theses arguments, some variables are set globaly:

        * ``glpi```: object for interacting with GLPI,
        * ``inventory```: the generated inventory
        * ``config``: groups configuration loaded from the configuration file
          passed as option
    """
    # args is returned as a dictionnary and contains the arguments with their
    # values. config is the configuration loaded from the configuration file
    # passed as option.
    global config
    args, config = init_cli()
    try:
        # Connect to GLPI API.
        global glpi
        glpi = GLPI(url=args['glpi_url'],
                    apptoken=args['glpi_apptoken'],
                    auth=args['glpi_usertoken'])

        # Initialize inventory.
        global inventory
        inventory = {'_meta': {'hostvars': {}},
                     'all': {'hosts': [], 'children': []}}

        # Recursively update inventory from configuration. Groups are popped
        # from config as they are parsed so this loop only pop root groups.
        while config:
            group = list(config.keys())[0]
            group_conf = config.pop(group)
            update_inventory_from_group(group, group_conf, parents_conf={})

        # Generate 'all' group from inventory.
        for group in set(inventory.keys()) - set(['all', 'ungrouped', '_meta']):
            inventory['all']['children'].append(group)
            inventory['all']['hosts'].extend(inventory[group].get('hosts', []))
        inventory['all']['hosts'] = sorted(set(inventory['all']['hosts']))

        # If --host option is used, return variables of the host generated by
        # the inventory.
        if args['host']:
            inventory = inventory['_meta']['hostvars'][args['host']]

        # Print inventory as JSON as required.
        print(json.dumps(inventory, indent=4))
    except GLPIError as err:
        print('unable to connect to GLPI: {:s}'.format(str(err)))
        sys.exit(1)
    except GLPIInventoryError as err:
        sys.stderr.write('error: {:s}\n'.format(str(err)))
        sys.exit(1)
    sys.exit(0)

#
# CLI
#
def init_cli():
    """Initialize CLI and load the configuration file.

    Parameters for connecting to GLPI can be managed by this CLI but the
    default values are set from theses environment variables:

    * ``ANSIBLE_GLPI_URL``: URL to the platform
    * ``ANSIBLE_GLPI_USERTOKEN``: User token (Administration -> Users
      -> <USER> -> ALL -> Remote access keys -> API token)
    * ``ANSIBLE_GLPI_APPTOKEN``: API client token (Setup -> General
      -> API -> <CLIENT> -> Application token (app_token))

    This returns the arguments as a dict and the groups configuration
    loaded from the configuration file.
    """
    parser = argparse.ArgumentParser(description='GLPI Inventory Module')

    # Options for connecting to GLPI.
    parser.add_argument('--glpi-url',
                        default=os.environ.get('ANSIBLE_GLPI_URL'),
                        help='URL for connecting to GLPI (default from '
                             'environment variable $ANSIBLE_GLPI_URL).')
    parser.add_argument('--glpi-usertoken',
                        default=os.environ.get('ANSIBLE_GLPI_USERTOKEN'),
                        help='User token for connecting to GLPI (default from '
                             'environment variable $ANSIBLE_GLPI_USERTOKEN).')
    parser.add_argument('--glpi-apptoken',
                        default=os.environ.get('ANSIBLE_GLPI_APPTOKEN'),
                        help='Password for connecting to GLPI (default from '
                             'environment variable $ANSIBLE_GLPI_APPTOKEN).')

    # Path to groups configuration file.
    config_path = os.path.join(os.path.dirname(__file__), 'glpi-api.yml')
    parser.add_argument('--config-file',
                        default=os.environ.get('ANSIBLE_GLPI_FILE', config_path),
                        metavar='GROUPS_CONFIG_PATH',
                        help='Groups configuration (default from environment '
                             'variable $ANSIBLE_GLPI_FILE or the file glpi-api.yml '
                             'beside this file)')

    # Ansible inventory options.
    ansible_group = parser.add_mutually_exclusive_group(required=True)
    ansible_group.add_argument('--list', action='store_true',
                               help='List active servers')
    ansible_group.add_argument('--host',
                               help='List details about the specific host')

    # Parse the CLI and retrieve arguments as dict (for being able to edit it).
    args = vars(parser.parse_args())

    # Ensure the parameters for connecting to GLPI are defined.
    missing_parameters = [arg
                          for arg in ('glpi_url', 'glpi_usertoken', 'glpi_apptoken')
                          if args[arg] is None]
    if missing_parameters:
        args_str = ', '.join('--{:s}'.format(arg.replace('_', '-'))
                             for arg in missing_parameters)
        parser.error('the following arguments are required: {:s}'.format(args_str))

    # Load groups configuration from configuration file. This is done here
    # for managing loading errors as a CLI error.
    try:
        with open(args['config_file']) as fhandler:
            groups_config = yaml.load(fhandler, Loader=yamlloader.ordereddict.CLoader)
    except (IOError, yaml.scanner.ScannerError) as err:
        parser.error('unable to load configuration file ({:s}):\n{:s}'
                     .format(args['config_file'], str(err)))

    return args, groups_config

#
# Inventory
#
def update_inventory_from_group(group, group_conf, parents_conf):
    """Recursively update ``inventory`` with group ``group`` and configuration
    ``group_conf``. ``parents_conf`` contains the parameters (`criteria`,
    `hostvars`, ...) merged from parents of the current group.

    ``group_conf`` is a structure (ie: a dictionary) containing theses parameters:

        * `itemtype`: item type for the GLPI request,
        * `criteria`: criteria for the GLPI request,
        * `metacriteria`: metacriteria for the GLPI request,
        * `fields`: list of fields number to retrieve for the GLPI
          request (`forcedisplay` parameter in the API request),
        * `hostname`: how to generate Ansible `inventory_hostname` variable for
          the hosts of the group from the data retrieved from the API
        * `vars`: Ansible `vars` for the group,
        * `hostvars`: Ansible host variables (`hostvars`; cummulating over groups!),
        * `children`: group children (which are recursively parsed),
        * `retrieve`: for intermediary groups, boolean for forcing the retrieval
          of hosts

    *hostname* and *hostvars* are generated from string in which fields number,
    prefixed by a dollar, are replaced by the corresponding values from retrieve
    data.
    """
    # Check input configuration.
    unknow_params = [param for param in group_conf if param not in GROUP_PARAMS]
    if unknow_params:
        raise GLPIInventoryError("group '{:s}' has invalid parameters: '{:s}'"
                                 .format(group, ', '.join(unknow_params)))

    # Get children list.
    children = group_conf.pop('children', [])
    if children:
        inventory.setdefault(group, {'children': children})

    # Update current group configuration with parents configuration.
    merge_parents_conf(group_conf, parents_conf)
    if group_conf['vars']:
        inventory.setdefault(group, {}).update(vars=group_conf['vars'])

    # Data are retrieved when there is no children or when 'retrieve'
    # parameter is set.
    retrieve = True if not children else group_conf.get('retrieve', False)
    if retrieve:
        update_inventory(group, group_conf)

    # For each children, pop child configuration from config and recursively
    # update inventory from child.
    for child in children:
        child_conf = config.pop(child)
        update_inventory_from_group(child, child_conf, group_conf)

def merge_parents_conf(group_conf, parents_conf):
    """Merge in-place ``group_conf`` with ``parents_conf``."""
    # Merge itemtype and hostname (set to None if not defined).
    for param in ('itemtype', 'hostname'):
        group_conf[param] = group_conf.get(param, parents_conf.get(param, None))

    # Merge criteria and metacriteria (set to an empty list if not defined).
    for param in ('criteria', 'metacriteria'):
        group_conf.setdefault(param, []).extend(parents_conf.get(param, []))

    # Map and merge 'forcedisplay' from 'fields' parameter (set to an empty
    # list if not defined).
    group_conf['forcedisplay'] = group_conf.pop('fields', [])
    group_conf['forcedisplay'].extend(parents_conf.get('forcedisplay', []))

    # Merge vars and hostvars parameters (set to an empty dict if not defined).
    for param in ('vars', 'hostvars'):
        group_conf[param] = group_conf.get(param, {})
        group_conf[param].update(parents_conf.get(param, {}))

def update_inventory(group, group_conf):
    """Update Ansible ``inventory`` with ``group`` based on ``group_conf``
    containing parameters for generating the API request and generating
    hostname, hostvars and vars values.
    """
    # Ensure we have at least an item type.
    if not group_conf.get('itemtype', None):
        raise GLPIInventoryError(
            "group '{:s}' has no itemtype defined when calling API"
            .format(group))

    # Retrieve data using GLPI API.
    data = glpi.search(itemtype=group_conf['itemtype'],
                       forcedisplay=group_conf['forcedisplay'],
                       criteria=group_conf['criteria'],
                       metacriteria=group_conf['metacriteria'],
                       range='0-9999')

    # Retrieve group's hosts and manage hostvars.
    hosts = []
    for entry in data:
        # Generate hostvars from the current entry.
        entry_hostvars = {param: replace_fields_values(value, entry)
                          for param, value in group_conf['hostvars'].items()}

        # Sometime returned host can be a list of host (as when retrieving
        # virtual machines). For preventing code redundancy, manage everything
        # as list.
        host = replace_fields_values(group_conf['hostname'], entry)
        if not isinstance(host, list):
            host = [host]
        # Add host to the list of hosts for the group add update hostvars
        # of the host in the inventory.
        for h in host:
            hosts.append(h.lower()) # Force host to be lowercase
            (inventory['_meta']['hostvars']
                .setdefault(h, {})
                .setdefault('glpi', {})
                .update(entry_hostvars))

    # Add group to inventory.
    if hosts:
        inventory.setdefault(group, {}).update(hosts=sorted(hosts))

def replace_fields_values(value, data, default=''):
    """Replace all occurences starting by a dollar and followed by a
    number with the corresponding field index in the data."""
    value = str(value)
    for field_idx in re.findall(r'\$(\d*)', value):
        # If current field is not defined or empty, add the default value.
        if not data[field_idx]:
            value = re.sub(r'\${}'.format(field_idx), default, value)
        # If the current field is a list, return it (all other elements
        # will be ignored).
        elif isinstance(data[field_idx], list):
            return data[field_idx]
        # Replace in string with the value from data.
        else:
            # Ugly hack for Python 2.7 and ensuring values are str/unicode.
            data_value = (unicode(data[field_idx])
                          if PY_VERSION < 3
                          else str(data[field_idx]))
            value = re.sub(r'\${}'.format(field_idx), data_value, value)
    return value

if __name__ == '__main__':
    main()