# coding: utf-8

import re
import os
import requests

# Initialize the library logger.
import logging
logger = logging.getLogger('glpi')
logger.setLevel(1)

class GLPIError(Exception):
    pass

# FIXME: context manager that execute kill_session at the end.

def _glpi_error(response):
    """GLPI errors message are returned in a list of two elements. The first
    element is the key of the error and the second the message."""
    raise GLPIError('({:s}) {}'.format(*response.json()))

def _unknown_error(response):
    """Helper for returning a HTTP code and response on non managed status code."""
    raise GLPIError('unknown error: {:d}/{:s}'
                    .format(response.status_code, response.text))

class GLPI:
    def __init__(self, url, apptoken, usertoken):
        logger.debug('GLPI url: {:s}'.format(url))
        self.url = url

        # Connect and retrieve token.
        session_token = self.init_session(apptoken, usertoken)
        self.session = requests.Session()

        # Set required headers.
        self.session.headers = {
            'Content-Type': 'application/json',
            'Session-Token': session_token,
            'App-Token': apptoken
        }

        # Use for caching field id/uid map.
        self.fields = {}

    def _catch_errors(func):
        """Decorator function for catching communication error
        and raising an exception."""
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except requests.exceptions.RequestException as err:
                raise GLPIError('communication error: {:s}'.format(str(err)))
        return wrapper

    def _set_method(self, *endpoints):
        return os.path.join(self.url, *[str(endpoint) for endpoint in endpoints])

    @_catch_errors
    def init_session(self, apptoken, usertoken):
        """Call initSession method that retrieve session token."""
        init_headers = {
            'Content-Type': 'application/json',
            'Authorization': 'user_token {:s}'.format(usertoken),
            'App-Token': apptoken
        }
        response = requests.get(url=self._set_method('initSession'),
                                headers=init_headers)

        return {
            200: lambda: response.json()['session_token'],
            400: lambda: _glpi_error(response),
            401: lambda: _glpi_error(response)
        }.get(response.status_code, lambda: _unknown_error(response))()

    @_catch_errors
    def kill_session(self):
        response = self.session.get(self._set_method('killSession'))
        {
            200: lambda: response.text,
            400: lambda: _glpi_error(response),
            401: lambda: _glpi_error(response)
        }.get(response.status_code, lambda: _unknown_error(response))()

    @_catch_errors
    def get_my_profiles(self):
        response = self.session.get(self._set_method('getMyProfiles'))
        return {
            200: lambda: response.json()['myprofiles'],
            400: lambda: _glpi_error(response),
            401: lambda: _glpi_error(response)
        }.get(response.status_code, lambda: _unknown_error(response))()

    @_catch_errors
    def get_active_profile(self):
        response = self.session.get(self._set_method('getActiveProfile'))
        return {
            200: lambda: response.json()['active_profile'],
            400: lambda: _glpi_error(response),
            401: lambda: _glpi_error(response)
        }.get(response.status_code, lambda: _unknown_error(response))()

    @_catch_errors
    def set_active_profile(self, profile_id):
        response = self.session.post(self._set_method('changeActiveProfile'),
                                     json={'profiles_id': profile_id})
        {
            200: lambda: None,
            400: lambda: _glpi_error(response),
            401: lambda: _glpi_error(response)
        }.get(response.status_code, lambda: _unknown_error(response))()

    @_catch_errors
    def get_my_entities(self):
        response = self.session.get(self._set_method('getMyEntities'))
        return {
            200: lambda: response.json()['myentities'],
            400: lambda: _glpi_error(response),
            401: lambda: _glpi_error(response)
        }.get(response.status_code, lambda: _unknown_error(response))()

    @_catch_errors
    def get_active_entities(self):
        response = self.session.get(self._set_method('getActiveEntities'))
        return {
            200: lambda: response.json()['active_entity'],
            400: lambda: _glpi_error(response),
            401: lambda: _glpi_error(response)
        }.get(response.status_code, lambda: _unknown_error(response))()

    @_catch_errors
    def set_active_entities(self, entity_id='all', is_recursive=False):
        data = {'entity_id': entity_id, 'is_recursive': is_recursive}
        response = self.session.post(self._set_method('changeActiveEntities'),
                                     json=data)
        return {
            200: lambda: None,
            400: lambda: _glpi_error(response),
            401: lambda: _glpi_error(response)
        }.get(response.status_code, lambda: _unknown_error(response))()

    @_catch_errors
    def get_full_session(self):
        response = self.session.get(self._set_method('getFullSession'))
        return {
            200: lambda: response.json()['session'],
            400: lambda: _glpi_error(response),
            401: lambda: _glpi_error(response)
        }.get(response.status_code, lambda: _unknown_error(response))()

    @_catch_errors
    def get_item(self, itemtype, item_id, **kwargs):
        response = self.session.get(self._set_method(itemtype, item_id),
                                    params=kwargs)
        return {
            200: lambda: response.json(),
            400: lambda: _glpi_error(response),
            401: lambda: _glpi_error(response),
            # If object is not found, return None.
            404: lambda: None
        }.get(response.status_code, lambda: _unknown_error(response))()

    @_catch_errors
    def get_all_items(self, itemtype, **kwargs):
        response = self.session.get(self._set_method(itemtype), params=kwargs)
        return {
            200: lambda: response.json(),
            206: lambda: response.json(),
            400: lambda: _glpi_error(response),
            401: lambda: _glpi_error(response)
        }.get(response.status_code, lambda: _unknown_error(response))()

    @_catch_errors
    def get_sub_items(self, itemtype, item_id, sub_itemtype, **kwargs):
        response = self.session.get(self._set_method(itemtype,
                                                     item_id,
                                                     sub_itemtype),
                                                     params=kwargs)
        return {
            200: lambda: response.json(),
            400: lambda: _glpi_error(response),
            401: lambda: _glpi_error(response)
        }.get(response.status_code, lambda: _unknown_error(response))()

    @_catch_errors
    def get_multiple_items(self, *items):
        def format_items(items):
            return {'items[{:d}][{:s}]'.format(idx, key): value
                    for idx, item in enumerate(items)
                    for key, value in item.items()}

        response = self.session.get(self._set_method('getMultipleItems'),
                                     params=format_items(items))
        return {
            200: lambda: response.json(),
            400: lambda: _glpi_error(response),
            401: lambda: _glpi_error(response)
        }.get(response.status_code, lambda: _unknown_error(response))()

    @_catch_errors
    def list_search_options(self, itemtype, raw=False):
        response = self.session.get(self._set_method('listSearchOptions', itemtype),
                                    params='raw' if raw else None)
        return {
            200: lambda: response.json(),
            400: lambda: _glpi_error(response),
            401: lambda: _glpi_error(response)
        }.get(response.status_code, lambda: _unknown_error(response))()

    def _map_fields(self, itemtype):
        fields = {}
        for field_id, field in self.list_search_options(itemtype).items():
            if 'uid' in field:
                field_uid = field['uid'].replace('{:s}.'.format(itemtype), '')
                fields.update({field_uid: field_id})
        return fields

    def field_id(self, itemtype, field_uid, refresh=False):
        """Return `itemtype` field id from `field_uid`. Each `itemtype`
        are "cached and will be retrieve once except if `refresh` is set.
        """
        if itemtype not in self.fields or refresh:
            # Generate field_uid: field_id map for item.
            self.fields[itemtype] = self._map_fields(itemtype)
        return self.fields[itemtype][field_uid]

    def field_uid(self, itemtype, field_id, refresh=False):
        """Return `itemtype` field uid from `field_uid`. Each `itemtype`
        are "cached and will be retrieve once except if `refresh` is set.
        """
        if itemtype not in self.fields or refresh:
            # Generate field_uid: field_id map for item.
            self.fields[itemtype] = self._map_fields(itemtype)
        return {value: key for key, value in self.fields[itemtype].items()}[field_id]

    @_catch_errors
    def search(self, itemtype, **kwargs):
        # Function for mapping field id from field uid if field_id is not a
        # number.
        def field_id(itemtype, field):
            return (int(field)
                    if str(field).isnumeric()
                    else self.field_id(itemtype, field))

        # Format 'criteria' and 'metacriteria' parameters.
        kwargs.update({'{:s}[{:d}][{:s}]'.format(param, idx, filter_param):
                        field_id(itemtype, value) if filter_param == 'field' else value
                       for param in ('criteria', 'metacriteria')
                       for idx, criterion in enumerate(kwargs.pop(param, []) or [])
                       for filter_param, value in criterion.items()})
        # Format 'forcedisplay' parameters.
        kwargs.update({'forcedisplay[{:d}]'.format(idx): field_id(itemtype, field)
                      for idx, field in enumerate(kwargs.get('forcedisplay', []) or [])})

        response = self.session.get(self._set_method('search', itemtype),
                                    params=kwargs)
        return {
            200: lambda: response.json().get('data', []),
            206: lambda: response.json().get('data', []),
            400: lambda: _glpi_error(response),
            401: lambda: _glpi_error(response)
        }.get(response.status_code, lambda: _unknown_error(response))()

    @_catch_errors
    def add(self, itemtype, *items):
        response = self.session.post(self._set_method(itemtype),
                                     json={'input': items})
        return {
            201: lambda: response.json(),
            207: lambda: response.json()[1],
            400: lambda: _glpi_error(response),
            401: lambda: _glpi_error(response)
        }.get(response.status_code, lambda: _unknown_error(response))()

    @_catch_errors
    def update(self, itemtype, *items):
        response = self.session.put(self._set_method(itemtype),
                                    json={'input': items})
        return {
            200: lambda: response.json(),
            207: lambda: response.json()[1],
            400: lambda: _glpi_error(response),
            401: lambda: _glpi_error(response)
        }.get(response.status_code, lambda: _unknown_error(response))()

    @_catch_errors
    def delete(self, itemtype, *items, **kwargs):
        response = self.session.delete(self._set_method(itemtype),
                                       params=kwargs,
                                       json={'input': items})
        return {
            200: lambda: response.json(),
            204: lambda: response.json(),
            207: lambda: response.json()[1],
            400: lambda: _glpi_error(response),
            401: lambda: _glpi_error(response)
        }.get(response.status_code, lambda: _unknown_error(response))()

if __name__ == '__main__':
    pass
    #print(glpi.get_my_profiles())
    #print(glpi.get_active_profile()['id'])
    #glpi.set_active_profile(4)
    #print(glpi.get_active_profile()['id'])
    #print()
    #print(glpi.get_my_entities())
    #pprint(glpi.get_active_entities())
    #glpi.set_active_entities(3)
    #print(glpi.get_my_entities())
    #pprint(glpi.get_active_entities())
    #pprint(glpi.get_full_session())

    #pprint(glpi.get_item('Computer', 1))
    #pprint(glpi.get_all_items('Computer'))
    #pprint(glpi.get_all_items('NetworkEquipment', range='0-10'))

    #pprint(glpi.get_multiple_items({'itemtype': 'Computer', 'items_id': 1},
    #                               {'itemtype': 'Computer', 'items_id': 2}))

    #pprint(glpi.list_search_options('Computer', raw=True))

    #pprint(glpi.search(
    #        itemtype='Computer',
    #        criteria=[
    #            {'link': 'AND', 'field': 45, 'searchtype': 'contains', 'value': '^CentOS$'},
    #            {'link': 'AND', 'field': 45, 'searchtype': 'contains', 'value': '^5'},
    #        ],
    #        range='10-20',
    #        forcedisplay=[1, 3, 160]))

    #print(glpi.add(
    #    'Computer',
    #    {'name': 'test', 'serial': 'toto'}
    #))

    #print(glpi.update(
    #    'Computer',
    #    {'id': 799, 'name': 'toto', 'serial': 'titi'}
    #))
