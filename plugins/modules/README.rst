************
GLPI modules
************

Exemple:

.. code::

  - name: Update GLPI informations of current host
    delegate_to: localhost
    unistra.glpi.api:
      url: "{{ lookup('env', 'ANSIBLE_GLPI_URL') }}"
      apptoken: "{{ lookup('env', 'ANSIBLE_GLPI_APPTOKEN') }}"
      auth:
        usertoken: "{{ lookup('env', 'ANSIBLE_GLPI_USERTOKEN') }}"
      itemtype: Computer
      criteria:
        80: 'Unistra > DNUM'
        1: "{{ inventory_hostname_short }}"
      values:
        states_id: 1      # Running
        entities_id: 1    # Unistra > DNUM
      state: present
      ignore_actions: [add, delete] # update only
