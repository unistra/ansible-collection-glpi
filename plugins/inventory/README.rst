**********************************
Ansible dynamic inventory for GLPI
**********************************

Generate an Ansible dynamic inventory from a configuration file describing
groups and how to generate them from GLPI API.

Usage
=====

First the plugin must be enabled in Ansible configuratin file:

.. code::

  $ vim ansible.cfg
  ...
  [inventory]
  enable_plugins = ...,unistra.glpi.inv
  ...

And to use it, you just need to pass the configuration file as input of the inventory:

.. code::

  $ ansible -i path/to/the/configuration/file.yml all --list-hosts

Configuration file
==================

.. code::

  ---
  ## Required
  plugin: unistra.glpi.inv

  ## Platform parameters (can also be passed as environment variables)
  glpi_url: https://<DOMAIN>/apirest.php
  glpi_apptoken:
  glpi_usertoken:
  # alternatively of the user token, username and password can be set.
  #glpi_username:
  #glpi_password:

  queries:

**Note:** Vaulted values can be used for theses parameters.

Queries
-------

Queries configuration is a dictionary containing **ordered** groups with theirs
definition. For managing the arborescence of groups, a `children` parameter is used
and the childs groups **need** to be defined after parents groups. Parameters are
merged at each level (ie: parameters of a parent group will be used by the child
group).

A group can contain theses parameters:

* `itemtype`: GLPI object type (*NetworkEquipment*, *Computer*, ...),
* `fields`: fields number (see *listSearchOptions* API method for the list of
  fields by object),
* `criteria`: search criteria,
* `metacriteria`: search metacriteria,
* `hostname`: indicate how to generate the hostname (Ansible *inventory_hostname*),
* `hostvars`: hostvars of hosts that are put, for each host, in the *glpi* key,
* `vars`: variables of the group,
* `children`: list of child groups,
* `retrieve`: force the retrieving of data

Some parameters are generated from the returned data based on field number. The
syntax *$FIELD_NUMBER* is used (exemple: *$1.$205* for generating FQDN from name
and domain).

Exemples
--------

* See `exemples/glpi-api.yml <https://github.com/unistra/ansible-collection-glpi/blob/master/exemples/glpi-api.yml>`_ for a complete exemple.

* Simple group with no child for retrieving all running network equipments:

.. code::

  nethosts:
    itemtype: NetworkEquipment
    fields: [1] # name
    criteria:
    - { link: 'AND', field: 31, searchtype: contains, value: '^Running$' }
    hostname: $1

* *hosts* group that sort hosts by OS type and version:

.. code::

  hosts:
    children: [unix, windows]
    itemtype: Computer
    fields:
    - 1   # name
    - 4   # ComputerType.name
    - 205  # Domain.name
    - 31  # State.completename
    criteria:
    - { link: AND, field: 31, searchtype: contains, value: '^Running$' }
    hostname: $1.$205  # Generate FQDN from hostname and domain
    hostvars:
      type: $4        # Set computer type to hostvars (`glpi.type`)
      state: $31      # Set state to hostvars (`glpi.state`)

  windows:
    children: [windows2008, windows2012, windows2016]
    criteria:
    - { link: AND, field: 45, searchtype: 'contains', value: 'Windows' }
    # Windows hosts use WinRM connection.
    vars:
      ansible_connection: winrm
      ansible_winrm_kinit_mode: managed # Kerberos ticket is managed by Ansible
      ansible_winrm_transport: kerberos
      ansible_port: 5986

  windows2008:
    criteria:
    - { link: AND, field: 46, searchtype: 'contains', value: '2008' }

  ...

  unix:
    children: [linux, bsd]
    # Unix/Linux hosts use SSH.
    vars:
      ansible_connection: ssh
      ansible_port: 22
      ansible_user: root

  linux:
    children: [ubuntu, centos]

  ubuntu:
    children: [ubuntu12, ubuntu14, ubuntu16, ubuntu18]
    criteria:
    - { link: AND, field: 45, searchtype: contains, value: '^Ubuntu$' }
    # Force retrieval of all ubuntu hosts even if we have children.
    retrieve: yes

  ubuntu12:
    criteria:
    - { link: AND, field: 46, searchtype: contains, value: '^12.04$' }

  ...

