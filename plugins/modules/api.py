#!/usr/bin/python
# coding: utf-8

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_native

import traceback
try:
    import glpi_api
    HAS_GLPI = True
except ImportError:
    HAS_GLPI = False

STATES = ['present', 'absent']

def core(module):
    state = module.params.pop('state')
    url = module.params.pop('url')
    apptoken = module.params.pop('apptoken')
    auth = module.params.pop('auth')
    itemtype = module.params.pop('itemtype')
    criteria = module.params.pop('criteria')
    values = module.params.pop('values')
    ignore_actions = module.params.pop('ignore_actions')

    try:
        with glpi_api.connect(url, apptoken, auth['usertoken']) as glpi:
            glpi_criteria = [
                {
                    'link': 'AND',
                    'field': field,
                    'searchtype': 'contains',
                    'value': '^{:s}$'.format(value)
                }
                for field, value in criteria.items()
            ]
            glpi_forcedisplay = ['id'] + list(criteria.keys())
            results = glpi.search(
                itemtype,
                criteria=glpi_criteria,
                forcedisplay=glpi_forcedisplay
            )

            if len(results) > 1:
                return {
                    'failed': True,
                    'msg': 'criteria must return only one result ({:d} returned)'
                           .format(len(results))
                }

            if len(results) == 0:
                if state == 'present':
                    # add
                    if 'add' in ignore_actions:
                        return {'changed': False, 'action': 'added',
                                'msg': "action ignored as specified by 'ignore_actions'"
                                       "parameter"}
                    glpi.add(itemtype, values)
                    return {'changed': True, 'action': 'added'}
                else:
                    # nothing
                    return {'changed': False, 'action': 'nothing'}
            else:
                item_id = results[0][glpi.field_id(itemtype, 'id')]
                if state == 'present':
                    # update
                    if 'update' in ignore_actions:
                        return {'changed': False, 'action': 'updated',
                                'msg': "action ignored as specified by 'ignore_actions'"
                                       "parameter"}
                    doc = {'id': item_id}
                    doc.update(values)
                    glpi.update(itemtype, doc)
                    return {'changed': True, 'action': 'updated'}
                else:
                    # delete
                    if 'delete' in ignore_actions:
                        return {'changed': False, 'action': 'updated',
                                'msg': "action ignored as specified by 'ignore_actions'"
                                       "parameter"}
                    glpi.delete(itemtype, {'id': item_id})
                    return {'changed': True, 'action': 'deleted'}

    except glpi_api.GLPIError as err:
        return {'failed': True, 'msg': to_native(err)}

def main():
    module = AnsibleModule(
        argument_spec = {
            'url': dict(type='str', required=True),
            'apptoken': dict(type='str', required=True),
            'auth': dict(type='dict', required=True),
            'state': dict(type='str', choices=STATES, default='present'),
            'itemtype': dict(type='str', required=True),
            'criteria': dict(type='dict', required=True),
            'values': dict(type='dict', required=False),
            'ignore_actions': dict(type='list', required=False, default=[])
        },
        supports_check_mode=False
    )

    if not HAS_GLPI:
        module.fail_json(msg="Missing required 'glpi_api' module")

    try:
        result = core(module)
    except Exception as err:
        module.fail_json(msg=to_native(err), exception=traceback.format_exc())

    if 'failed' in result:
        module.fail_json(**result)
    else:
        module.exit_json(**result)

if __name__ == '__main__':
    main()
