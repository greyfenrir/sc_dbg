import os
import logging
import inspect

import sys
from unittest.case import TestCase

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)


def __dir__():
    filename = inspect.getouterframes(inspect.currentframe())[1][1]
    return os.path.dirname(filename)


RESOURCES_DIR = __dir__() + '/resources/'


class CloudTestCase(TestCase):  # just to trigger logging config
    pass
