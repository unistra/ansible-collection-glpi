***************************
Ansible collection for GLPI
***************************

Note: At start this repository contains only a JSON inventory. This script has been moved
to *scripts/inventory* for legacy.

This collection contains:

* a dynamic inventory (see `inventory README </plugins/inventory/README.rst>`_)
* a module for interacting with GLPI (see `modules README </plugins/modules/README.rst>`__)

To install the collection:

.. code::

  # set collections directory to the current directory (default is ~/.ansible/collections)
  $ export ANSIBLE_COLLECTIONS_PATH=$(pwd)
  $ ansible-galaxy collection install git+https://github.com/unistra/ansible-collection-glpi,collection
