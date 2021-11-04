import os
import re
from ansible.plugins.inventory import BaseInventoryPlugin
from ansible.module_utils._text import to_native
from ansible.errors import AnsibleError
from glpi_api import GLPI, GLPIError

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

def replace_fields_values(value, data, default=''):
    '''
    Helper function that replace all occurences starting by a dollar and followed
    by a number with the corresponding field index in the data.
    '''
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
            #data_value = (unicode(data[field_idx])
            #              if PY_VERSION < 3
            #              else str(data[field_idx]))
            data_value = to_native(data[field_idx])
            value = re.sub(r'\${}'.format(field_idx), data_value, value)
    return value

def merge_parents_conf(group_conf, parents_conf):
    '''
    Helper function that merge, in-place, ``group_conf`` and ``parents_conf``.
    '''
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

class InventoryModule(BaseInventoryPlugin):
    NAME = 'unistra.glpi.glpi'

    def verify_file(self, path):
        ''' return true/false if this is possibly a valid file for this plugin to consume '''
        valid = False
        if super(InventoryModule, self).verify_file(path):
            # base class verifies that file exists and is readable by current user
            if path.endswith(('.yaml', '.yml')):
               valid = True
        return valid

    def parse(self, inventory, loader, path, cache=True):
        super(InventoryModule, self).parse(inventory, loader, path, cache)
        config = self._read_config_data(path)

        glpi_url = config.get('glpi_url', os.environ.get('GLPI_URL'))
        glpi_apptoken = config.get('glpi_apptoken', os.environ.get('GLPI_APPTOKEN'))
        glpi_usertoken = config.get('glpi_usertoken', os.environ.get('GLPI_USERTOKEN'))
        glpi_username = config.get('glpi_username', os.environ.get('GLPI_USERNAME'))
        glpi_password = config.get('glpi_password', os.environ.get('GLPI_PASSWORD'))

        if glpi_url is None:
            raise AnsibleError('GLPI url not provided')

        if glpi_apptoken is None:
            raise AnsibleError('GLPI application token not provided')

        if glpi_usertoken is not None:
            # Force str for vaulted string
            glpi_auth = str(glpi_usertoken)
        else:
            if glpi_username is None or glpi_password is None:
                raise AnsibleError('GLPI auth invalid: usertoken or username/password required ')
            # Force str for vaulted strings
            glpi_auth = (str(glpi_username), str(glpi_password))

        try:
            # Force str for vaulted strings
            self.glpi = GLPI(url=str(glpi_url), apptoken=str(glpi_apptoken), auth=glpi_auth)

            # Recursively update inventory from configuration. Groups are popped
            # from config as they are parsed so this loop only pop root groups.
            self.queries = config['queries']
            while self.queries:
                group = list(self.queries.keys())[0]
                group_conf = self.queries.pop(group)
                self.update_inventory_from_group(group, group_conf, parents_conf={})
        except GLPIError as err:
            raise AnsibleError('GLPI error: {:s}'.format(to_native(err)))

    def update_inventory_from_group(self, group, group_conf, parents_conf):
        """Recursively update ``inventory`` with group ``group`` and self.queries
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
            raise AnsibleError(
                "group '{:s}' has invalid parameters: '{:s}'"
                .format(group, ', '.join(unknow_params))
            )

        # Get children list.
        children = group_conf.pop('children', [])
        if children:
            self.inventory.add_group(group)
            [self.inventory.add_group(child) for child in children]
            [self.inventory.add_child(group, child) for child in children]

        # Update current group configuration with parents configuration.
        merge_parents_conf(group_conf, parents_conf)
        if group_conf['vars']:
            [
                self.inventory.set_variable(group, var, value)
                for var, value in group_conf['vars'].items()
            ]

        # Data are retrieved when there is no children or when 'retrieve'
        # parameter is set.
        retrieve = True if not children else group_conf.get('retrieve', False)
        if retrieve:
            self.update_inventory(group, group_conf)

        # For each children, pop child configuration from config and recursively
        # update inventory from child.
        for child in children:
            child_conf = self.queries.pop(child)
            self.update_inventory_from_group(child, child_conf, group_conf)

    def update_inventory(self, group, group_conf):
        """Update Ansible ``inventory`` with ``group`` based on ``group_conf``
        containing parameters for generating the API request and generating
        hostname, hostvars and vars values.
        """
        # Ensure we have at least an item type.
        if not group_conf.get('itemtype', None):
            raise AnsibleError(
                "group '{:s}' has no itemtype defined when calling API"
                .format(group)
            )

        # Retrieve data using GLPI API.
        data = self.glpi.search(
            itemtype=group_conf['itemtype'],
            forcedisplay=group_conf['forcedisplay'],
            criteria=group_conf['criteria'],
            metacriteria=group_conf['metacriteria'],
            range='0-9999'
        )

        # Retrieve group's hosts and manage hostvars.
        self.inventory.add_group(group)
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
                #hosts.append(h.lower()) # Force host to be lowercase
                self.inventory.add_host(h, group=group)
                self.inventory.set_variable(h, 'glpi', entry_hostvars)
