# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import errno
import os
import socket
import time
import traceback
import urlparse
from abc import ABCMeta, abstractmethod

import mozprocess

from .base import get_free_port, cmd_arg


__all__ = ["SeleniumLocalServer", "ChromedriverLocalServer"]


class LocalServer(object):
    __metaclass__ = ABCMeta

    used_ports = set()
    path_prefix = "/"

    def __init__(self, logger, binary, port=None, path_prefix=None):
        self.logger = logger
        self.binary = binary
        self.port = port
        if path_prefix is not None:
            self.path_prefix = path_prefix

        if self.port is None:
            self.port = get_free_port(4444, exclude=self.used_ports)
        self.used_ports.add(self.port)
        self.url = "http://127.0.0.1:%i%s" % (self.port, self.path_prefix)

        self.proc = None

    @abstractmethod
    def command(self):
        pass

    @property
    def environ(self):
        return os.environ.copy()

    def start(self):
        self.logger.debug("Running %s" % " ".join(self.command))
        self.proc = mozprocess.ProcessHandler(self.command,
                                              processOutputLine=self.on_output,
                                              env=self.environ)
        try:
            self.proc.run()
        except OSError as e:
            if e.errno == errno.ENOENT:
                raise IOError(
                    "webdriver executable not found: %s" % self.binary)
            raise

        self.logger.debug(
            "Waiting for server to become accessible: %s" % self.url)
        surl = urlparse.urlparse(self.url)
        addr = (surl.hostname, surl.port)
        try:
            wait_service(addr)
        except:
            self.logger.error(
                "Server was not accessible within the timeout:\n%s" % traceback.format_exc())
            raise
        else:
            self.logger.info("Server running with pid %i listening on port %i" % (self.pid, self.port))

    def stop(self):
        if hasattr(self.proc, "proc"):
            self.proc.kill()

    def is_alive(self):
        if hasattr(self.proc, "proc"):
            return self.proc.poll() is None
        return False

    def on_output(self, line):
        self.logger.process_output(self.pid,
                                   line.decode("utf8", "replace"),
                                   command=" ".join(self.command))

    @property
    def pid(self):
        if hasattr(self.proc, "proc"):
            return self.proc.pid


class SeleniumLocalServer(LocalServer):
    path_prefix = "/wd/hub"

    def __init__(self, logger, binary, port=None):
        LocalServer.__init__(self, logger, binary, port=port)

    @property
    def command(self):
        return ["java", "-jar", self.binary, "-port", str(self.port)]

    def start(self):
        self.logger.debug("Starting local Selenium server")
        LocalServer.start(self)

    def stop(self):
        LocalServer.stop(self)
        self.logger.info("Selenium server stopped listening")


class ChromedriverLocalServer(LocalServer):
    path_prefix = "/wd/hub"

    def __init__(self, logger, binary="chromedriver", port=None, path_prefix=None):
        LocalServer.__init__(self, logger, binary, port=port, path_prefix=path_prefix)

    @property
    def command(self):
        # TODO: verbose logging
        return [self.binary,
                cmd_arg("port", str(self.port)) if self.port else "",
                cmd_arg("url-base", self.path_prefix) if self.path_prefix else ""]

    def start(self):
        self.logger.debug("Starting local chromedriver server")
        LocalServer.start(self)

    def stop(self):
        LocalServer.stop(self)
        self.logger.info("chromedriver server stopped listening")

class WiresLocalServer(LocalServer):
    def __init__(self, logger, binary, marionette_port, port=None, path_prefix=None):
        LocalServer.__init__(self, logger, binary, port=port, path_prefix=path_prefix)
        self.marionette_port = marionette_port

    @property
    def command(self):
        return [self.binary,
                cmd_arg("connect-existing"),
                cmd_arg("webdriver-port", str(self.port)),
                cmd_arg("marionette-port", str(self.marionette_port))]

    @property
    def environ(self):
        env = os.environ.copy()
        env["RUST_LOG"] = "debug"
        return env

def wait_service(addr, timeout=60):
    """Waits until network service given as a tuple of (host, port) becomes
    available or the `timeout` duration is reached, at which point
    ``socket.error`` is raised."""
    end = time.time() + timeout
    so = socket.socket()
    while end > time.time():
        try:
            so.connect(addr)
        except socket.timeout:
            pass
        except socket.error as e:
            if e[0] != errno.ECONNREFUSED:
                raise
            time.sleep(0.5)
        else:
            so.shutdown(socket.SHUT_RDWR)
            so.close()
            return True

    raise socket.error("Service is unavailable: %s:%i" % addr)
