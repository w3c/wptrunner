# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from .base import Browser, ExecutorBrowser, require_arg
from .webdriver import EdgeLocalServer
from ..executors import executor_kwargs as base_executor_kwargs
from ..executors.executoredge import (EdgeTestharnessExecutor,
                                      EdgeRefTestExecutor)
from ..environment import LocalServerEnvironment

__wptrunner__ = {"product": "edge",
                 "check_args": "check_args",
                 "browser": "EdgeBrowser",
                 "executor": {"testharness": "EdgeTestharnessExecutor",
                              "reftest": "EdgeRefTestExecutor"},
                 "env": "LocalServerEnvironment",
                 "browser_kwargs": "browser_kwargs",
                 "executor_kwargs": "executor_kwargs",
                 "env_options": "env_options"}


def check_args(**kwargs):
    require_arg(kwargs, "webdriver_binary")


def browser_kwargs(**kwargs):
    return {"webdriver_binary": kwargs["webdriver_binary"]}

def executor_kwargs(test_type, server_config, cache_manager, run_info_data,
                    **kwargs):
    executor_kwargs = base_executor_kwargs(test_type, server_config,
                                           cache_manager, **kwargs)
    executor_kwargs["close_after_done"] = True

    return executor_kwargs

def env_options():
    return {"host": "web-platform.test",
            "bind_hostname": "false",
            "testharnessreport": "testharnessreport-edge.js",
            "supports_debugger": False}

class EdgeBrowser(Browser):
    used_ports = set()

    def __init__(self, logger, webdriver_binary):
        Browser.__init__(self, logger)
        self.driver = EdgeLocalServer(self.logger, binary=webdriver_binary)
        self.webdriver_host = "localhost"
        self.webdriver_port = self.driver.port
        
    def start(self):
        self.driver.start()

    def stop(self):
        self.driver.stop()

    def pid(self):
        return self.driver.pid

    def is_alive(self):
        # TODO(ato): This only indicates the driver is alive,
        # and doesn't say anything about whether a browser session
        # is active.
        return self.driver.is_alive()

    def cleanup(self):
        self.stop()

    def executor_browser(self):
        return ExecutorBrowser, {"webdriver_host": self.webdriver_host,
                                 "webdriver_port": self.webdriver_port}
