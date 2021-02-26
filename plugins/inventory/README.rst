**********************************
Ansible dynamic inventory for GLPI
**********************************

**/!\\This documentation is for the JSON plugin and has still not been updated when it was
transformed to a dedicated plugin. See** `this
<https://github.com/unistra/ansible-collection-glpi/issues/3#issuecomment-743413045>`__
**for an up to date exemple/!\\**

Generate an Ansible dynamic inventory from a configuration file describing
groups and how to generate them from GLPI API.

Installation
============

Theses python modules must be installed on the controller:

* `pyyaml <https://pypi.org/project/pyyaml>`_ for manipulating YAML files
* `yamlloader <https://pypi.org/project/yamlloader/>`_ for keeping configuration
  order
* `glpi <https://github.com/unistra/python-glpi-api>`_ for interacting with GLPI
  REST API

There is a requirements file containing these dependencies so, if you don't care
about clean integration to the system (using virtualenvs, distribution packages,
...):

.. code::

      $ sudo pip install -r requirements.txt

Configuration file
==================

The configuration is a hash containing groups with theirs definition. For
managing the arborescence of groups, a `children` parameter is used and the
childs groups **need** to be defined after parents groups. Parameters are merged
at each level (ie: parameters of a parent group will be used by the child
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
syntax *$FIELD_NUMBER* is used (exemple: *$1.$33* for generating FQDN from name
and domain).

Exemples
--------

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
      - 33  # Domain.name
      - 31  # State.completename
      criteria:
      - { link: AND, field: 31, searchtype: contains, value: '^Running$' }
      hostname: $1.$33  # Generate FQDN from hostname and domain
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

Usage
=====

The command-line take theses options:

* `--glpi-url`: GLPI URL (default from `ANSIBLE_GLPI_URL` environment variable).
* `--glpi-apptoken`: API client token for connecting to the API (default from
  `ANSIBLE_GLPI_APPTOKEN` environment variable; see Setup -> General -> API
  -> <CLIENT> -> Application token (app_token)).
* `--glpi-usertoken`: User token for connecting to the API (default from
  `ANSIBLE_GLPI_USERTOKEN` environment variable; see Administration -> Users
  -> <USER> -> ALL -> Remote access keys -> API token).
* `--config-file`: Path to the configuration file (default from `ANSIBLE_GLPI_FILE`
  environment variable or the *glpi-api.yml* beside the python file).
* `--list`: Required Ansible option that generate the inventory.
* `--host`: Return an host inventory (this generate the complete inventory and
  returns the information of the specified host).

Standalone
----------

.. note::

      You can use `jq <https://stedolan.github.io/jq/>`__ which is
      an awesome tool for parsing JSON (which is returned by the dynamic
      inventory).

.. code::

      $ ./glpi-api.py --list | jq '.' | less


With Ansible
------------

Ad-Hoc
~~~~~~

Fox example, execute `uname -a` on all unix hosts:

.. code::

      $ ansible -i glpi-api.py unix -m command -a 'uname -a'

Playbook
~~~~~~~~

Same example with a playbook:

.. code::

      $ vim playbook.yml
      ---
      - hosts: unix
        gather_facts: no
        tasks:
        - name: Execute uname
          command: uname -a

      $ ansible-playbook -i glpi-api.py playbook.yml
