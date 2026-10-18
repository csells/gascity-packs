import unittest
from unittest.mock import Mock

from full_e2e import Runner


class PersonalContractTests(unittest.TestCase):
    def test_personal_project_gets_an_empty_native_picker_and_a_launcher_conversation(self):
        runner = Runner.__new__(Runner)
        runner.manifest = {"projectId": "proj_mapped", "workspaces": {"global": "/work/global"}}
        runner.agent = Mock(return_value={"id": "gc1_global"})
        runner.browser = Mock(return_value={"status": "no-models", "gasCityCatalogs": [{"url": "u", "models": 0}]})
        runner.conversation = Mock(return_value={"thread_id": "thr_1", "turns": 2})
        evidence = runner.personal_contract()
        runner.browser.assert_called_once_with("native.personal-picker", {"id": "gc1_global"}, "proj_personal",
                                               "/work/global", until="no-models")
        runner.conversation.assert_called_once_with("native.personal", "global", project="proj_mapped", route="launcher")
        self.assertEqual(evidence["thread_id"], "thr_1")
        self.assertEqual(evidence["gas_city_catalogs"], [{"url": "u", "models": 0}])


if __name__ == "__main__":
    unittest.main()
