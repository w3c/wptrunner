import time

from tools.webdriver import TestBase

class Test(TestBase):
    def test_pass(self):
        self.force_new_session()

    def test_fail(self):
        self.force_new_session()

    def test_error(self):
        raise Exception

    def test_disabled(self):
        raise Exception

class TestTimeout(TestBase):
    def test_timeout(self):
        time.sleep(20)
