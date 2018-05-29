import logging
import os
import tempfile

from bzt.engine import ScenarioExecutor, Configuration, Engine
from bzt.modules.aggregator import AggregatorListener


class ModuleMock(ScenarioExecutor):
    pass


class EngineEmul(Engine):
    """
    emulating engine
    """

    def __init__(self):
        super(EngineEmul, self).__init__(logging.getLogger(''))
        self.config.merge({"provisioning": "local"})
        art_dir_pattern = os.path.dirname(__file__) + "/../build/test/%Y-%m-%d_%H-%M-%S.%f"
        self.config.get('settings', force_set=True)['artifacts-dir'] = art_dir_pattern
        self.create_artifacts_dir()
        self.finalize_exc = None
        self.was_finalize = False

    def dump_config(self):
        """ test """
        fname = tempfile.mkstemp()[1]
        self.config.dump(fname, Configuration.JSON)
        with open(fname) as fh:
            logging.debug("JSON:\n%s", fh.read())

    def merge_local_jmeter_path(self):
        """ to fix relative paths """
        dirname = os.path.dirname(__file__)
        self.config.merge({
            "modules": {
                "jmeter": {
                    "path": dirname + "/../build/jmeter/bin/jmeter",
                },
                "grinder": {
                    "path": dirname + "/../build/grinder",
                },
                "gatling": {
                    "path": dirname + "/../build/gatling/bin/gatling.sh",
                }
            }
        })


class ResultChecker(AggregatorListener):
    def __init__(self, callback):
        super(ResultChecker, self).__init__()
        self.callback = callback

    def aggregated_second(self, data):
        self.callback(data)
