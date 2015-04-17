# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import json
import os
import socket
import sys
import threading
import time
import traceback
import urlparse
import uuid

from .base import (ExecutorException,
                   Protocol,
                   RefTestExecutor,
                   RefTestImplementation,
                   TestExecutor,
                   TestharnessExecutor,
                   testharness_result_converter,
                   reftest_result_converter,
                   strip_server)
from .executorselenium import (SeleniumProtocol,
                               SeleniumTestharnessExecutor,
                               SeleniumRefTestExecutor)
from ..testrunner import Stop


here = os.path.join(os.path.split(__file__)[0])

webdriver = None
exceptions = None

extra_timeout = 5

class SeleniumRemoteProtocol(SeleniumProtocol):
    def after_connect(self):
        pass


class SeleniumRemoteTestharnessExecutor(SeleniumTestharnessExecutor):
    def __init__(self, browser, server_config, timeout_multiplier=1,
                 close_after_done=True, capabilities=None, debug_info=None):
        SeleniumTestharnessExecutor.__init__(self, browser, server_config, timeout_multiplier=1,
                                             close_after_done=True, capabilities=None,
                                             debug_info=None)
        self.protocol = SeleniumRemoteProtocol(self, browser, capabilities)
        self.script = None

    def on_protocol_change(self, new_protocol):
        pass

    def do_testharness(self, webdriver, url, timeout):
        #TODO don't reset this timeout all the time
        webdriver.implicitly_wait(timeout)
        webdriver.get(url)
        #TODO Consider just using one remote script and mutation observers here
        try:
            webdriver.find_element_by_id("__testharness__results__")
        except exceptions.NoSuchElement:
            raise exceptions.TimeoutException
        text = webdriver.execute_script("return document.getElementById('__testharness__results__').textContent")
        self.logger.debug(text)
        result = json.loads(text)
        del result["test"]
        return result


class SeleniumRemoteRefTestExecutor(SeleniumRefTestExecutor):
    def __init__(self, *args, **kwargs):
        SeleniumRefTestExecutor.__init__(self, *args, **kwargs)
        self.close_after_done = False

    def is_alive(self):
        return self.protocol.is_alive()

    def do_test(self, test):
        self.logger.info("Test requires OS-level window focus")

        if not self.has_window:
            self.protocol.webdriver.set_window_size(800, 600)
            self.has_window = True

        result = self.implementation.run_test(test)

        return self.convert_result(test, result)

    def screenshot(self, test):
        return SeleniumRun(self._screenshot,
                           self.protocol.webdriver,
                           self.test_url(test),
                           test.timeout).run()

    def _screenshot(self, webdriver, url, timeout):
        webdriver.get(url)

        webdriver.execute_async_script(self.wait_script)

        screenshot = webdriver.get_screenshot_as_base64()

        # strip off the data:img/png, part of the url
        if screenshot.startswith("data:image/png;base64,"):
            screenshot = screenshot.split(",", 1)[1]

        return screenshot
