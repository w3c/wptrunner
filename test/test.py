import ConfigParser
import json
import os
import sys
import tempfile
import threading
import time
from StringIO import StringIO

from mozlog.structured import get_default_logger, reader
from wptrunner import wptcommandline, wptrunner

here = os.path.abspath(os.path.dirname(__file__))

class ResultHandler(reader.LogHandler):
    def __init__(self):
        self.ran = 0
        self.failed = []

    def test_status(self, data):
        self.test_end(data)

    def test_end(self, data):
        self.ran += 1
        if "expected" in data:
            self.failed.append(data)

def test_settings():
    return {
        "include": "_test",
        "manifest-update": ""
    }

def read_config():
    parser = ConfigParser.ConfigParser()
    parser.read("test.cfg")

    rv = {"general":{},
          "products":{}}

    rv["general"].update(dict(parser.items("general")))

    # This only allows one product per whatever for now
    for product in parser.sections():
        if product != "general":
            rv["products"][product] = dict(parser.items(product))

    return rv

def run_tests(product, settings):
    parser = wptcommandline.create_parser()
    kwargs = vars(parser.parse_args(settings_to_argv(settings)))
    wptcommandline.check_args(kwargs)

    result_handler = ResultHandler()
    wptrunner.setup_logging({"log_mach":[sys.stdout]}, {})
    get_default_logger().add_handler(result_handler)

    kwargs["test_paths"]["/_test/"] = {"tests_path": os.path.join(here, "testdata"),
                                       "metadata_path": os.path.join(here, "metadata")}

    wptrunner.run_tests(**kwargs)

    print "Product %s ran %d tests, failed %s" % (product, result_handler.ran,
                                                  len(result_handler.failed))

def settings_to_argv(settings):
    rv = []
    for name, value in settings.iteritems():
        rv.append("--%s" % name)
        if value:
            rv.append(value)
    return rv

def main():
    config = read_config()

    for product, product_settings in config["products"].iteritems():
        settings = test_settings()
        settings.update(config["general"])
        settings.update(product_settings)
        settings["product"] = product
        run_tests(product, settings)

if __name__ == "__main__":
    import pdb, traceback
    try:
        main()
    except Exception:
        print traceback.format_exc()
        pdb.post_mortem()
