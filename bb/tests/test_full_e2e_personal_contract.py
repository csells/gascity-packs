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


class FixtureBindingTests(unittest.TestCase):
    def test_fixture_project_is_bound_at_city_scope_to_its_own_workspace(self):
        from types import SimpleNamespace
        from full_e2e_browser_cases import bind_fixture_project
        calls = []
        runner = SimpleNamespace(manifest={"hostId": "host_1", "cityName": "city-a", "commands": {"gc": "/bin/gc"}},
                                 bb=lambda *args: calls.append(("bb", *args)) or {"id": "proj_fixture"},
                                 command=lambda *args: calls.append(("cmd", *args)) or "")
        self.assertEqual(bind_fixture_project(runner, "e2e-fixture", "/work/fixture_ws"), "proj_fixture")
        self.assertEqual(calls, [
            ("bb", "project", "create", "--name", "e2e-fixture", "--root", "/work/fixture_ws", "--host", "host_1", "--json"),
            ("cmd", "/bin/gc", "bb", "bind", "--project", "proj_fixture", "--city", "city-a", "--path", "/work/fixture_ws")])


if __name__ == "__main__":
    unittest.main()
