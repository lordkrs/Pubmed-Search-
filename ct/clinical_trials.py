#!/usr/bin/env python

"""
Python wrapper for the Clincal Trials API.

Clinical Trials Documentation:  http://clinicaltrials.gov/ct2/info/linking
"""

import os
import imp
import re
import sys
try:
    from urllib import quote
except ImportError:
    from urllib.parse import quote

try:
    import json
except ImportError:  # pragma: no cover
    # For older versions of Python.
    import simplejson as json

try:
    from urllib import urlencode
except ImportError:  # pragma: no cover
    # For Python 3.
    from urllib.parse import urlencode

try:
    from urllib2 import urlopen
except ImportError:  # pragma: no cover
    # For Python 3.
    from urllib.request import urlopen

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ct.xml2dict import xml2dict


class API(object):
    """An example class for a Python API wrapper."""

    def __init__(self, api_key=''):
        if api_key:
            self.api_key = api_key
        self.base_url = ''
        self.output_format = None
        self.required_params = None

    def call_api(self, directory=None, **kwargs):
        """
        A generic example api wrapping method. Other methods can use this
        method to interact with the API.
        """
        self._check_base_url()
        url_list = [self.base_url]
        if directory:
            url_list.append('/%s' % directory)
        if self.required_params:
            kwargs.update(self.required_params)
        try:
            output_format = kwargs.pop('output_format')
        except KeyError:
            output_format = self.output_format
        if kwargs:
            params = urlencode(kwargs)
            url_list.extend(['?', params])
        url = ''.join(url_list)
        data = urlopen(url).read()
        return self._format_data(output_format, data)

    def _check_base_url(self):
        """Internal method to format `self.base_url`."""
        base_url = self.base_url
        if base_url and base_url.endswith('/'):
            base_url = base_url.rstrip('/')
            self.base_url = base_url

    def _format_data(self, output_format, data):
        """Internal method to return formatted data to developer."""
        if output_format:
            # Check for cases people capitalize JSON or XML.
            output_format =  output_format.lower()
        if output_format == 'json':
            # Turn JSON into a dictionary.
            return json.loads(data)
        elif output_format == 'xml':
            return self._xml_to_dict(data)
        return data

    def _xml_to_dict(self, xml):
        """
        Internal method to turn XML to dictionary output. Developers can
        overwrite this method to use their favorite XML parser of choice.
        """
        return xml2dict(xml)



class Trials(API):
    """Python wrapper for the Clinical Trials API."""

    def __init__(self):
        super(Trials, self).__init__()
        self.base_url = 'http://clinicaltrials.gov'
        self.output_format = 'xml'
        self.required_params = {'displayxml': 'true'}
        self.search_types_dict = {
            'condition': 'cond', 'conditions': 'cond',
            'intervention': 'intr', 'interventions': 'intr',
            'outcome': 'outc', 'outcomes': 'outc',
            'sponsor': 'spons', 'sponsors': 'spons',
            'country': 'cntry1', 'state': 'state1',
            'recruiting': 'recr'
        }
        # Save compiled regular expressions.
        self._re_state = re.compile('state.*')
        self._re_country = re.compile('(country|cntry).*')
        self._re_country_num = re.compile('country(.+)')

    def search(self, search_term=None, search_type='term', **kwargs):
        """
        Search the Clinical Trials database.

        >>> Trials().search('pediatric')
        """
        if search_term:
            kwargs.update({search_type: search_term})
        kwargs = self._correct_keywords(**kwargs)
        return self.call_api('search', **kwargs)

    def _correct_keywords(self, **kwargs):
        """Internal method to loop through and correct keyword arguments."""
        search_types_dict = self.search_types_dict
        for key in kwargs:
            if self._re_state.match(key):
                state_abbrev = kwargs[key]
                kwargs[key] = 'NA:US:' + state_abbrev
            elif self._re_country.match(key):
                country_abbrev = kwargs[key]
                if len(country_abbrev) == 2:
                    # We haven't seen it before.
                    kwargs[key] = 'NA:' + country_abbrev
            if key in search_types_dict:
                # We need to go from human readable to the
                # correct search_type parameter name.
                correct_name = search_types_dict[key]
                data = kwargs.pop(key)
                kwargs.update({correct_name: data})
            elif self._re_country_num.match(key):
                # Then someone put in a keyword like `country3`.
                country_abbrev = kwargs.pop(key)
                formatted_key = self._re_country_num.sub(r'cntry\1', key)
                kwargs.update({formatted_key: country_abbrev})
        return kwargs

    def download(self, search_term=None, search_type='term', **kwargs):
        """
        Download a ZIP file of XML files pertaining to your search.

        >>> Trials().download("alzheimer's disease", count=50)
        """
        self.required_params = {'studyxml': 'true', 'output_format': None}
        zip_data = self.search(search_term, search_type, **kwargs)
        self.required_params = {'displayxml': 'true'}
        return zip_data
