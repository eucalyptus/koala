=============================
Eucalyptus Management Console
=============================

.. image:: https://travis-ci.org/eucalyptus/eucaconsole.svg?branch=master
    :target: https://travis-ci.org/eucalyptus/eucaconsole

The Eucalyptus Management Console is a web-based interface to a local Eucalyptus cloud and/or AWS services.


AWS Services supported
======================

* EC2
* Auto Scaling
* CloudWatch
* S3
* IAM

Issue Tracking
==============

For bug reports, improvement request and general project planning, we use Jira: https://eucalyptus.atlassian.net/

To obtain the latest development source code for the eucalyptus management console, visit
https://github.com/eucalyptus/eucaconsole.  Pull requests are welcome and appreciated.  By submitting code to the
eucalyptus management console, you agree that code will be licensed under the 2-clause BSD license.  A copy of
this license is included in the COPYING file that accompanies the source code.


Development environment setup
=============================

Prerequisites
-------------
Prior to installing Pyramid and its dependencies, you may need to install the following libraries...

* libevent-dev (required by gevent)
* openssl (required by M2Crypto)
* gcc, python development headers, swig (required to install Python libraries)

Ubuntu:

    `apt-get install openssl build-essential python-dev swig memcached libmemcached6`

Fedora:

    `yum install openssl-devel python-devel swig memcached libmemcached; yum groupinstall 'Development tools'`

OS X:

Install homebrew, then run

    `brew install libevent openssl swig libmagic memcached libmemcached`

Pyramid Setup
-------------
Run `python setup.py develop` to set up the development environment.
This only needs to be run once or when the "requires" package versions in setup.py are modified.

Note: It is strongly recommended to set up the development environment in a virtualenv.

If setup.py fails with an M2Crypto error and you're on a yum-based system (Fedora, CentOS, RHEL),
download the M2Crypto package at https://pypi.python.org/pypi/M2Crypto and install via `fedora_setup.sh install`


Sass/Compass Setup
------------------
The CSS files are pre-processed using Sass, so you'll need to set up a Sass-to-CSS watcher to output CSS.

To set up Compass as the file watcher...

::

    sudo gem install compass
    cd eucaconsole/static
    compass watch .

Once you have installed compass, there's a handy shortcut to enable the watcher.  From the repo root...

    make watch

Note that as of Foundation 5.5, Sass 3.4 and Compass 1.0 or later are required.  Older versions will not work.
To install the proper versions of Sass and Compass, run the following commands at the root of this repo...

::

    sudo gem install bundler
    bundle install


See http://bundler.io/bundle_install.html for more info about Bundler and using a Gemfile


Running the management console
==============================
To run the server, you will need to specify the path to the config file (console.ini).
Copy the default ini file to the application root.  At the repo root...

    cp conf/console.default.ini ./console.ini

The default settings assume an HTTPS/SSL environment.  To disable HTTPS/SSL, set session.secure to false in console.ini

    session.secure = false

The session keys are written to a file specified in console.ini.
You may need to change the session.keyini setting if you don't have write access to the default location,
or you may comment out the following line to have the session keys generated at the repo root.

    session.keyini = /etc/eucaconsole/session-keys.ini

Run the server with

    ./launcher.sh

`launcher.sh` is provided as an alias for `pserve console.ini --reload`


Compilation Issues on OS X
--------------------------
On OS X (Yosemite and El Capitan), you may encounter issues installing M2Crypto and/or gevent.

There is a known bug in the M2Crypto bindings and swig versions greater than 3.0.4.
Using Homebrew you may install swig 3.0.4...

::

    brew uninstall swig
    brew install homebrew/versions/swig304
    python setup.py develop
    ./launcher.sh

If there are issues with M2Crypto locating the OpenSSL libraries (which could happen after an XCode update),
reinstall the XCode Command Line Tools  via `xcode-select --install`

If gevent has trouble compiling, use `CFLAGS='-std=c99' pip install gevent` as a workaround



Running the server in development/debug mode
--------------------------------------------
The launcher.sh script runs the application with gunicorn and gevent,
closely matching the production deployment setup.

To have Pyramid automatically detect modifications to templates and views,

1. Change the reload_templates setting to true in console.ini: `pyramid.reload_templates = true`
2. Run the server with the --reload flag: `pserve console.ini --reload`

The `--reload` flag instructs Pyramid to automatically watch for changes in the view callables.

Note: Waitress may work better than gunicorn with the --reload flag.  To install Waitress, run `pip install -e .[dev]`
(this will also install the Pyramid Debug Toolbar).

To switch from gunicorn to Waitress for development, change the server:main section in your console.ini to this:

::

    [server:main]
    use = egg:waitress#main
    host = 0.0.0.0
    port = 8888

The Pyramid Debug Toolbar can be enabled by adding pyramid_debugtoolbar to the app:main section of console.ini

::

    [app:main]
    # ...
    pyramid.includes =
        pyramid_beaker
        pyramid_chameleon
        pyramid_debugtoolbar
        pyramid_layout

You may also find it useful to set the logging level to DEBUG in the console.ini config file...

::

    [logger_root]
    # ...
    handlers = logfile, screen_debug

The management console assumes an SSL setup. To disable SSL for development purposes, set `session.secure = false`
in the config file (console.ini)


Running the server in production mode
-------------------------------------
A production deployment assumes an SSL setup, requiring nginx. To configure nginx...

1. Copy the nginx.conf file at conf/nginx.conf to your system's nginx.conf location
    - Location is usually /etc/nginx/nginx.conf on Linux and /usr/local/etc/nginx/nginx.conf on OS X
2. Configure SSL (specify paths to certificate and key files)
3. Visit the site via an HTTPS url (e.g. https://localhost)


Running the tests
-----------------
The unit tests are based on Python's standard unittest library.

To run all tests, run the following at the repo root:

    python setup.py test

To run the tests with nose and report test coverage:

    python setup.py nosetests --with-coverage

Note that you will need to `pip install nose, coverage, nose-cov` to use nose with coverage

To run a single test (this is not obvious with nose integrated with setup.py)::

    python setup.py nosetests --tests tests.somepkg.somemodule


Configuring i18n
----------------
The translation strings are marked in templates and in python scripts as decribed at
http://docs.pylonsproject.org/projects/pyramid/en/latest/narr/i18n.html#i18n-chapter

The translations require Babel and lingua, which can be install via `pip install -e .[i18n]`

To generate the translation files, run 'make translations' at the repo root.

To contribute translations, follow the instructions at
https://github.com/eucalyptus/eucaconsole/wiki/Contributing-Translations


Technology Stack
================

Primary Components
------------------
* Pyramid
* Boto
* Zurb Foundation
* AngularJS

Secondary Components
--------------------
* Beaker and pyramid_beaker (server-side cache/sessions)
* Chameleon (server-side templates)
* pyramid_layout (layout/themes for Pyramid)
* Waitress or gunicorn (WSGI server)
* WTForms (server-side forms and validation)


Guitester - selenium testing framework for eucaconsole
======================================================
* Location: tests/selenium/guiops
* Requirements: python selenium module, an instance of selenium webdriver
* Setup and intro: https://github.com/eucalyptus/eucaconsole/wiki/Guitester 
* Contributing: https://github.com/eucalyptus/eucaconsole/wiki/Contributing-to-Guitester


Grunt - JavaScript Task Manager
===============================

Grunt Setup
-----------
* At home directory `./eucaconsole`
* Install npm if missing: 
::

    yum install -y npm

* Run 
::

    npm install

to install npm packages listed in the file `package.json`
::
    npm install -g grunt-cli

to allow grunt cli to run

Grunt Task File
---------------
::

    Gruntfile.js

Grunt Commands
--------------
* Default:
::

    grunt
    
* Bowercopy:
::

    grunt bowercopy

* Karma:
::

    grunt karma
    
* Karma(Single run):
::

    grunt karma:ci


Bower - JavaScript Package Manager
==================================

Bower Setup
-----------
* See Grunt Setup above

Bower Configuration File
------------------------
* List the versions of the JS packages
::

    bower.json

* ex.
::

    "dependencies": {
        "angular": "1.2.26",
        "angular-sanitize": "1.2.26",
        "angular-mocks": "1.2.26",
        "jquery": "2.0.3",
        "jasmine": "2.0.3",
        "jasmine-jquery": "2.0.5"
      }

Bowercopy Configuration File
----------------------------
* List the destination for the files to be copied after running bower
::

    Gruntfile.js

* ex.
::

      bowercopy: {
          angular: {
              options: {
                  destPrefix: 'eucaconsole/static/js/thirdparty/angular'
              },
              files: {
                'angular.min.js': 'angular/angular.min.js',
                'angular-sanitize.min.js': 'angular-sanitize/angular-sanitize.min.js',
                'angular-mocks.js': 'angular-mocks/angular-mocks.js'
              }
          },


Run Bowercopy
-------------
* Runs bower to download the JS packages and move the files in place
::

    grunt bowercopy


Jasmine & Karma - JavaScript Unittest & test runner
===================================================

Jasmine & Karma Setup
---------------------
* See Grunt Setup above


Karma Configuration File
------------------------
::

    karma.conf.js

* ex.
::

    files: [
      'templates/panels/*.pt',
      'static/js/thirdparty/modernizr/custom.modernizr.js',
      'static/js/thirdparty/jquery/jquery.min.js',
      'static/js/thirdparty/angular/angular.min.js',
      'static/js/thirdparty/angular/angular-sanitize.min.js',
      'static/js/thirdparty/angular/angular-mocks.js',
      'static/js/thirdparty/jquery/jquery.generateFile.js',
      'static/js/widgets/notify.js',
      'static/js/pages/eucaconsole_utils.js',
      'static/js/thirdparty/jquery/chosen.jquery.min.js',
      'static/js/thirdparty/jasmine/jasmine-jquery.js',
      'static/js/pages/custom_filters.js',
      'static/js/widgets/tag_editor.js',
      'static/js/widgets/securitygroup_rules.js',
      'static/js/pages/keypair.js',
      'static/js/jasmine-spec/SpecHelper.js',
      'static/js/jasmine-spec/spec_security_group_rules.js',
      'static/js/jasmine-spec/spec_keypair.js',
      'static/js/jasmine-spec/spec_tag_editor.js'
    ],


Jasmine Spec File Location
--------------------------
::

    ./eucaconsole/static/js/jasmine-spec/

Run Karma
---------
::

    grunt karma

Run Karma (Single Run)
----------------------
::

    grunt karma:ci

See the wiki page https://github.com/eucalyptus/eucaconsole/wiki/JavaScript-UnitTest-Submit-Guideline for more details.

