# Copyright 2011 The greplin-tornado-ses Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""API for Amazon SES"""

import hmac
import hashlib
import base64
import functools
import urllib
import logging

from datetime import datetime

from tornado import httpclient



class AmazonSes(object):
  """Amazon SES object"""

  BASE_URL = 'https://email.us-east-1.amazonaws.com'


  def __init__(self, access_key, secret_id):
    self._access_key = access_key
    self._secret_id = secret_id


  def _sign(self, message):
    """Sign an AWS request"""
    signed_hash = hmac.new(key=self._secret_id, msg=message, digestmod=hashlib.sha256)
    return base64.b64encode(signed_hash.digest()).decode()


  def _call(self, command, callback, extra_params=None):
    """Make a call to SES"""
    params = extra_params or {}
    params['Action'] = command
    now = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
    headers = {
      'Content-Type':'application/x-www-form-urlencoded',
      'Date':now,
      'X-Amzn-Authorization':'AWS3-HTTPS AWSAccessKeyId=%s, Algorithm=HMACSHA256, Signature=%s' %
                             (self._access_key, self._sign(now))
    }
    http = httpclient.AsyncHTTPClient()
    http.fetch(self.BASE_URL, functools.partial(self._on_request_completed, callback),
               headers=headers, method="POST",
               body=urllib.urlencode(params))


  def _on_request_completed(self, callback, result):
    """Parse a request"""
    if result.code == 200:
      callback(True)
      return
    logging.error("Amazon SES: %s", result.body)
    callback(None)


  def send_mail(self, source, subject, body, to_addresses,
                cc_addresses=None, bcc_addresses=None, email_format='text',
                callback=None, reply_addresses=None, return_path=None):
    """Composes an email and sends it"""
    known_formats = {
      'html':'Message.Body.Html.Data',
      'text':'Message.Body.Text.Data'
    }
    singular = {
      'Source': source,
      'Message.Subject.Data':subject
    }
    if email_format not in known_formats:
      raise ValueError("Format must be either 'text' or 'html'")
    singular[known_formats[email_format]] = body
    if return_path:
      singular['ReturnPath'] = return_path
    multiple = AwsMultipleParameterContainer()
    multiple['Destination.ToAddresses.member'] = to_addresses
    if cc_addresses:
      multiple['Destination.CcAddresses.member'] = cc_addresses
    if bcc_addresses:
      multiple['Destination.BccAddresses.member'] = bcc_addresses
    if reply_addresses:
      multiple['ReplyToAddresses.member'] = reply_addresses
    params = dict(singular, **multiple)
    callback = callback or (lambda x: True)
    self._call('SendEmail', callback, params)





class AwsMultipleParameterContainer(dict):
  """Build a parameters list as required by Amazon"""


  def __setitem__(self, key, value):
    if isinstance(value, basestring):
      value = [value]
    for i in range(1, len(value) + 1):
      dict.__setitem__(self, '%s.%d' % (key, i), value[i - 1])

