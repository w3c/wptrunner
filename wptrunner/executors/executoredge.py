import json
import os
import time
import traceback

import webdriver
from base import strip_server, RefTestImplementation, RefTestExecutor
from executorservodriver import (ServoWebDriverProtocol,
                                 ServoWebDriverRun,
                                 ServoWebDriverTestharnessExecutor)


here = os.path.join(os.path.split(__file__)[0])

extra_timeout = 5

class EdgeWebDriverProtocol(ServoWebDriverProtocol):
    pass

class EdgeWebDriverRun(ServoWebDriverRun):
    pass

class EdgeTestharnessExecutor(ServoWebDriverTestharnessExecutor):
    def __init__(self, browser, server_config, timeout_multiplier=1,
                 close_after_done=True, capabilities=None, debug_info=None):
        ServoWebDriverTestharnessExecutor.__init__(self, browser, server_config, timeout_multiplier=1, close_after_done=True, capabilities=None, debug_info=None)
        self.protocol = EdgeWebDriverProtocol(self, browser, capabilities=capabilities)
        with open(os.path.join(here, "testharness_edge.js")) as f:
            self.script = f.read()
        self.timeout = None

    def on_protocol_change(self, new_protocol):
        pass

    def is_alive(self):
        return self.protocol.is_alive()

    def do_test(self, test):
        url = self.test_url(test)

        timeout = test.timeout * self.timeout_multiplier + extra_timeout

        if timeout != self.timeout:
            try:
                self.protocol.session.timeouts.script = timeout
                self.timeout = timeout
            except IOError:
                self.logger.error("Lost webdriver connection")
                return Stop

        success, data = EdgeWebDriverRun(self.do_testharness,
                                         self.protocol.session,
                                         url,
                                         timeout).run()

        if success:
            return self.convert_result(test, data)

        return (test.result_cls(*data), [])

    def do_testharness(self, session, url, timeout):
        try:
            session.url = url
            t0 = time.time()
            while time.time() - t0 < timeout:
                result = session.execute_script(self.script)
                if result is not None:
                    print result
                    return json.loads(result)
                time.sleep(0.1)
        except Exception as e:
            print traceback.format_exc()
            raise
        #Status 2 here is TIMEOUT
        return [strip_server(url), 2, None, None, []]

    

class EdgeRefTestExecutor(RefTestExecutor):
    def __init__(self, browser, server_config, timeout_multiplier=1,
                 screenshot_cache=None, capabilities=None, debug_info=None,
                 close_after_done=True):
        """Selenium WebDriver-based executor for reftests"""
        RefTestExecutor.__init__(self,
                                 browser,
                                 server_config,
                                 screenshot_cache=screenshot_cache,
                                 timeout_multiplier=timeout_multiplier,
                                 debug_info=debug_info)
        self.protocol = EdgeWebDriverProtocol(self, browser, capabilities=capabilities)
        self.implementation = RefTestImplementation(self)
        self.timeout = None
        with open(os.path.join(here, "reftest-wait_edge.js")) as f:
            self.wait_script = f.read()

    def do_test(self, test):
        try:
            result = self.implementation.run_test(test)
            return self.convert_result(test, result)
        except IOError:
            return test.result_cls("CRASH", None), []
        except TimeoutError:
            return test.result_cls("TIMEOUT", None), []
        except Exception as e:
            message = getattr(e, "message", "")
            if message:
                message += "\n"
            message += traceback.format_exc(e)
            return test.result_cls("ERROR", message), []

    def is_alive(self):
        return self.protocol.is_alive()
            
    def screenshot(self, test):
        timeout = (test.timeout * self.timeout_multiplier + extra_timeout
                   if self.debug_info is None else None)

        if self.timeout != timeout:
            try:
                self.protocol.session.timeouts.script = timeout
                self.timeout = timeout
            except IOError:
                self.logger.error("Lost webdriver connection")
                return Stop

        return EdgeWebDriverRun(self._screenshot,
                                self.protocol.session,
                                self.test_url(test),
                                timeout).run()


    def _screenshot(self, session, url, timeout):
        session.url = url
        t0 = time.time()
        while time.time() - t0 < timeout:
            if session.execute_script(self.wait_script):
                return session.screenshot()
            time.sleep(0.1)
        #TODO
        raise webdriver.TimeoutException


