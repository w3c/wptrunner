# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import hashlib
import json
import os
import traceback
from abc import ABCMeta, abstractmethod
from multiprocessing import Manager

from ..testrunner import Stop

here = os.path.split(__file__)[0]

cache_manager = Manager()

def executor_kwargs(test_type, http_server_url, **kwargs):
    timeout_multiplier = kwargs["timeout_multiplier"]
    if timeout_multiplier is None:
        timeout_multiplier = 1

    executor_kwargs = {"http_server_url": http_server_url,
                       "timeout_multiplier": timeout_multiplier}
    if test_type == "reftest":
        executor_kwargs["screenshot_cache"] = cache_manager.dict()
    return executor_kwargs


class TestharnessResultConverter(object):
    harness_codes = {0: "OK",
                     1: "ERROR",
                     2: "TIMEOUT"}

    test_codes = {0: "PASS",
                  1: "FAIL",
                  2: "TIMEOUT",
                  3: "NOTRUN"}

    def __call__(self, test, result):
        """Convert a JSON result into a (TestResult, [SubtestResult]) tuple"""
        assert result["test"] == test.url, ("Got results from %s, expected %s" %
                                            (result["test"], test.url))
        harness_result = test.result_cls(self.harness_codes[result["status"]], result["message"])
        return (harness_result,
                [test.subtest_result_cls(subtest["name"], self.test_codes[subtest["status"]],
                                         subtest["message"]) for subtest in result["tests"]])
testharness_result_converter = TestharnessResultConverter()


def reftest_result_converter(self, test, result):
    return (test.result_cls(result["status"], result["message"],
                            extra=result.get("extra")), [])


class TestExecutor(object):
    __metaclass__ = ABCMeta

    test_type = None
    convert_result = None

    def __init__(self, browser, http_server_url, timeout_multiplier=1):
        """Abstract Base class for object that actually executes the tests in a
        specific browser. Typically there will be a different TestExecutor
        subclass for each test type and method of executing tests.

        :param browser: ExecutorBrowser instance providing properties of the
                        browser that will be tested.
        :param http_server_url: Base url of the http server on which the tests
                                are running.
        :param timeout_multiplier: Multiplier relative to base timeout to use
                                   when setting test timeout.
        """
        self.runner = None
        self.browser = browser
        self.http_server_url = http_server_url
        self.timeout_multiplier = timeout_multiplier
        self.protocol = None # This must be set in subclasses

    @property
    def logger(self):
        """StructuredLogger for this executor"""
        if self.runner is not None:
            return self.runner.logger

    def setup(self, runner):
        """Run steps needed before tests can be started e.g. connecting to
        browser instance

        :param runner: TestRunner instance that is going to run the tests"""
        self.runner = runner
        self.protocol.setup(runner)

    def teardown(self):
        """Run cleanup steps after tests have finished"""
        self.protocol.teardown()

    def run_test(self, test):
        """Run a particular test.

        :param test: The test to run"""
        try:
            result = self.do_test(test)
        except Exception as e:
            self.logger.debug(traceback.format_exc(e))
            result = self.result_from_exception(test, e)

        if result is Stop:
            return result

        print result
        if result[0].status == "ERROR":
            self.logger.debug(result[0].message)
        self.runner.send_message("test_ended", test, result)

    @abstractmethod
    def do_test(self, test):
        """Test-type and protocol specific implmentation of running a
        specific test.

        :param test: The test to run."""

    def result_from_exception(self, test, e):
        if hasattr(e, "status") and e.status in ReftestResult.statuses:
            status = e.status
        else:
            status = "ERROR"
            message = e.message + "\n" + traceback.format_exc(e)
        return test.result_cls(status, message), []


class TestharnessExecutor(TestExecutor):
    convert_result = testharness_result_converter


class RefTestExecutor(TestExecutor):
    convert_result = reftest_result_converter

    def __init__(self, browser, http_server_url, timeout_multiplier=1, screenshot_cache=None):
        TestExecutor.__init__(self, browser, http_server_url,
                              timeout_multiplier=timeout_multiplier)

        self.screenshot_cache = screenshot_cache

class RefTestImplementation(object):
    def __init__(self, executor):
        self.timeout_multiplier = executor.timeout_multiplier
        self.executor = executor
        # Cache of url:(screenshot hash, screenshot). Typically the
        # screenshot is None, but we set this value if a test fails
        # and the screenshot was taken from the cache so that we may
        # retrieve the screenshot from the cache directly in the future
        self.cache = executor.screenshot_cache

    def get_hash(self, url, timeout):
        timeout = timeout * self.timeout_multiplier

        if url not in self.cache:
            success, data = self.executor.screenshot(url, timeout)

            if not success:
                return False, data

            screenshot = data
            hash_value = hashlib.sha1(screenshot).hexdigest()

            self.cache[url] = (hash_value, None)

            return True, (hash_value, screenshot)

        return True, self.hash_cache[url]

    def is_pass(self, lhs_hash, rhs_hash, relation):
        assert relation in ("==", "!=")
        self.executor.logger.debug("Testing %s %s %s" %(lhs_hash, relation, rhs_hash))
        return ((relation == "==" and lhs_hash == rhs_hash) or
                (relation == "!=" and lhs_hash != rhs_hash))

    def run_test(self, test):
        success, data = self.get_hash(test.url, test.timeout)

        if success is False:
            return {"status":data[0], "message": data[1]}

        lhs_node = test
        lhs_hash, lhs_screenshot = data

        # Depth-first search of reference tree, with the goal
        # of reachings a leaf node with only pass results

        stack = list(reversed(test.references))
        while stack:
            rhs_node, relation = stack.pop()
            success, data = self.get_hash(rhs_node.url, rhs_node.timeout)

            if success is False:
                return {"status":data[0], "message": data[1]}

            rhs_hash, rhs_screenshot = data

            if self.is_pass(lhs_hash, rhs_hash, relation):
                if rhs_node.references:
                    stack.extend(list(reversed(rhs_node.references)))
                else:
                    # We passed
                    return {"status":"PASS", "message": None}
            elif stack:
                # Continue to the next option
                lhs_node = rhs_node
                lhs_hash = rhs_hash
                lhs_screenshot = rhs_screenshot

        if lhs_screenshot is None:
            lhs_screenshot = self.retake_screenshot(lhs_node)

        if rhs_screenshot is None:
            rhs_success, rhs_screenshot = self.executor.screenshot(rhs_node.url,
                                                                   rhs_node.timeout *
                                                                   self.timeout_multiplier)

        log_data = [{"url": lhs_node.url, "screenshot": lhs_screenshot}, relation,
                    {"url": rhs_node.url, "screenshot": rhs_screenshot}]

        return {"status":"FAIL", "message": None,
                "extra": {"reftest_screenshots": log_data}}

class Protocol(object):
    def __init__(self, executor, browser, http_server_url):
        self.executor = executor
        self.browser = browser
        self.http_server_url = http_server_url

    @property
    def logger(self):
        return self.executor.logger

    def setup(self, runner):
        pass

    def teardown(self):
        pass
