# -*- coding: utf-8 -*-
"""
  Wikipedia channel for IFTTT
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~

  Copyright 2015 Ori Livneh <ori@wikimedia.org>,
                 Stephen LaPorte <stephen.laporte@gmail.com>,
            
            2016 Alangi Derick <alangiderick@gmail.com>

  Licensed under the Apache License, Version 2.0 (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.

"""

import flask
from urllib import urlencode
from flask import request, render_template, g
from flask import redirect, url_for
from flask_material import Material 

from .utils import snake_case
from .triggers import (ArticleOfTheDay,
                       PictureOfTheDay,
                       WordOfTheDay,
                       ArticleRevisions,
                       UserRevisions,
                       NewArticle,
                       NewHashtag,
                       NewCategoryMember,
                       CategoryMemberRevisions,
                       ItemRevisions,
                       PopularPersonsBirthday)

import logging
LOG_FILE = 'ifttt.log'
logging.basicConfig(filename=LOG_FILE,
                    format='%(asctime)s - %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p',
                    level=logging.DEBUG)


ALL_TRIGGERS = [ArticleOfTheDay,
                PictureOfTheDay,
                WordOfTheDay,
                ArticleRevisions,
                UserRevisions,
                NewArticle,
                NewHashtag,
                NewCategoryMember,
                CategoryMemberRevisions,
                ItemRevisions,
                PopularPersonsBirthday]

app = flask.Flask(__name__)
material = Material(app)
# Load default config first
app.config.from_pyfile('../default.cfg', silent=True)
# Override defaults if ifttt.cfg is present
app.config.from_pyfile('../ifttt.cfg', silent=True)

# Creating a custom filter
app.jinja_env.filters['urlencode'] = lambda params: urlencode(params)


@app.errorhandler(400)
def missing_field(e):
    """There was something wrong with incoming data from IFTTT. """
    error = {'message': 'missing required trigger field'}
    return flask.jsonify(errors=[error]), 400


@app.errorhandler(401)
def unauthorized(e):
    """Issue an HTTP 401 Unauthorized response with a JSON body."""
    error = {'message': 'Unauthorized'}
    return flask.jsonify(errors=[error]), 401

@app.errorhandler(404)
def page_not_found(e):
    """The page you are looking for is not found on the server"""
    g.skip_after_request = True
    return render_template('error_pages/404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    """There was an internal server error"""
    g.skip_after_request = True
    return render_template('error_pages/500.html'), 500


@app.after_request
def force_content_type(response):
    """RFC 4627 stipulates that 'application/json' takes no charset parameter,
    but IFTTT expects one anyway. We have to twist Flask's arm to get it to
    break the spec."""
    if g.get('skip_after_request'):
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
        return response
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    return response


@app.before_request
def validate_channel_key():
    """Verify that the 'IFTTT-Channel-Key' header is present on each request
    and that its value matches the channel key we got from IFTTT. If a request
    fails this check, we reject it with HTTP 401."""
    if flask.request.method == 'GET' and flask.request.endpoint != 'status':
        return
    channel_key = flask.request.headers.get('IFTTT-Channel-Key')
    if not app.debug and channel_key != app.config.get('CHANNEL_KEY'):
        flask.abort(401)


@app.route('/ifttt/v1/test/setup', methods=['POST'])
def test_setup():
    """Required by the IFTTT endpoint test suite."""
    ret = {'samples': {'triggers': {}}}
    for trigger in ALL_TRIGGERS:
        trigger_name = snake_case(trigger.__name__)
        if trigger.default_fields:
            ret['samples']['triggers'][trigger_name] = trigger.default_fields
    return flask.jsonify(data=ret)


@app.route('/ifttt/v1/rss-feeds')
def index():
    """Return the list of feeds in material design card template"""
    feeds = {'samples': {'feeds': {}}}
    # Sum the ALL_TRIGGERS list
    list_count = len(ALL_TRIGGERS)
    for feed in ALL_TRIGGERS:
        feed_name = snake_case(feed.__name__)
        feed_display_name = feed_name.replace("_", " ").capitalize()
        if feed.default_fields:
            feeds['samples']['feeds'][feed_display_name] = feed.default_fields

    # Set skip_after_request through the g object to True 
    # so that the Content-Type returned will be plain text 
    # for the HTML in feeds.html to render correctly and not 
    # in JSON format as the flask default Content-Type.
    g.skip_after_request = True
    return render_template('index.html', data=feeds, count=list_count)


@app.route('/ifttt/v1/status')
def status():
    """Return HTTP 200 and an empty body, as required by the IFTTT spec."""
    return ''


for view_class in ALL_TRIGGERS:
    slug = getattr(view_class, 'url_pattern', None)
    if not slug:
        slug = snake_case(view_class.__name__)
    app.add_url_rule('/ifttt/v1/triggers/%s' % slug,
                     view_func=view_class.as_view(slug))
