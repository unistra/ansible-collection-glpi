***************************
Ansible collection for GLPI
***************************

**Note:** At the start this repository contains only a JSON inventory. The script has been
moved to `scripts/inventory <https://github.com/unistra/ansible-collection-glpi/tree/master/scripts/inventory>`_ for legacy.

This collection contains:

* a dynamic inventory (see `inventory README </plugins/inventory/README.rst>`_)
* a module for interacting with GLPI (see `modules README </plugins/modules/README.rst>`__)

Installation
============

Theses python modules must be installed on the controller:

* `pyyaml <https://pypi.org/project/pyyaml>`_ for manipulating YAML files
* `yamlloader <https://pypi.org/project/yamlloader>`_ for keeping configuration
  order
* `glpi-api <https://pypi.org/project/glpi-api>`_ for interacting with GLPI
  REST API

There is a requirements file containing these dependencies so, if you don't care
about clean integration to the system (using virtualenvs, distribution packages,
...):

.. code::

      $ sudo pip install -r requirements.txt

To install the collection:

.. code::

  # set collections directory to the current directory (default is ~/.ansible/collections)
  $ export ANSIBLE_COLLECTIONS_PATH=$(pwd)
  $ ansible-galaxy collection install git+https://github.com/unistra/ansible-collection-glpi,1.0.0

With a requirements file:

.. code::

  $ vim requirements.yml
  ---
  collections:
  - name: https://github.com/unistra/ansible-collection-glpi
    type: git
    version: 1.0.0

  $ ansible-galaxy install -r requirements.yml
