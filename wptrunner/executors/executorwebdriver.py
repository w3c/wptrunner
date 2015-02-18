# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import inspect
import os
import sys
import socket
import time
import traceback

from .base import TestExecutor, Protocol

def webdriver_result_converter(self, test, result):
    return (test.result_cls(result["status"], result["message"],
                            extra=result.get("extra")),
            [test.subtest_result_cls(subtest["name"], subtest["status"],
                                     subtest["message"]) for subtest in result["tests"]])

class WebDriverTestExecutor(TestExecutor):
    test_type = "webdriver"
    convert_result = webdriver_result_converter

    def __init__(self, browser, http_server_url, timeout_multiplier=1,
                 debug_args=None):
        """
        :param browser: ExecutorBrowser instance providing properties of the
                        browser that will be tested.
        :param http_server_url: Base url of the http server on which the tests
                                are running.
        :param timeout_multiplier: Multiplier relative to base timeout to use
                                   when setting test timeout.
        """
        TestExecutor.__init__(self, browser, http_server_url, timeout_multiplier=1,
                              debug_args=None)
        self.protocol = Protocol(self, browser, http_server_url)

    def do_test(self, test):
        """Test-type and protocol specific implementation of running a
        specific test.

        :param test: The test to run."""
        url, test_class_name = test.url.rsplit("#", 1)

        path = os.path.join(test.test_root, test.path)

        rv = None

        if not os.path.exists(path):
            rv = {"status": "ERROR",
                  "message": "Test file %s does not exist" % path,
                  "tests": []}

        if rv is None:
            environ = {"__file__": path}
            try:
                self.logger.debug("Loading %s" % path)
                execfile(path, environ, environ)
            except Exception as e:
                rv = {"status": "ERROR",
                      "message": "Error loading tests:\n%s" % traceback.format_exc(e),
                      "tests": []}

        if rv is None:
            if test_class_name in environ:
                test_class = environ[test_class_name]
                try:
                    with TestRunner(test_class, self.config) as runner:
                        subtest_results = runner.run_all()
                        rv = {"status": "OK",
                              "message": None,
                              "tests": subtest_results}
                except Exception as e:
                    rv = {"status":"ERROR",
                          "message": traceback.format_exc(e),
                          "tests":[]}
            else:
                rv = {"status": "ERROR",
                      "message": "Test class %s not found:\n%r" % (test_class, environ.keys()),
                      "tests": []}

        return self.convert_result(test, rv)


#TODO: impose a timeout on each test
class TestRunner(object):
    def __init__(self, test_class, config):
        self.test_obj = test_class(config)

    def __enter__(self):
        if hasattr(self.test_obj, "setup"):
            self.test_obj.setup()
        return self

    def __exit__(self, *args, **kwargs):
        #TODO: Error handling
        if hasattr(self.test_obj, "teardown"):
            self.test_obj.teardown()

    @property
    def test_methods(self):
        def is_test_method(item):
            return callable(item) and item.__name__.startswith("test_")

        return inspect.getmembers(self.test_obj, is_test_method)

    def run_all(self):
        return [self.run_test(name, method) for name, method in self.test_methods]


    def run_test(self, name, method):
        try:
            method()
        except AssertionError as e:
            result = {"name": name,
                      "status":"FAIL",
                      "message": getattr(e, "message")}
        except Exception as e:
            result = {"name": name,
                      "status":"ERROR",
                      "message": traceback.format_exc(e)}
        else:
            result = {"name": name,
                      "status":"PASS",
                      "message": None}
        return result
