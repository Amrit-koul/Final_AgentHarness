import json
import tempfile
import unittest
from pathlib import Path

import yaml

from agent_harness.prompt_registry import PromptRegistry, PromptRegistryError
from banking_agents.prompts import prompt_registry


class PromptRegistryTests(unittest.TestCase):
    def test_required_demo_prompts_load_with_hash_and_metadata(self):
        prompt_ids = set(prompt_registry.list_prompt_ids())
        expected = {
            "intent_classifier",
            "orchestrator",
            "task_decomposer",
            "policy_assistant_system",
            "policy_assistant_retrieval_answer",
            "policy_navigator",
            "loan_eligibility_reasoning",
            "collections_advisor",
            "collections_behavioral_prediction",
            "collections_call_copilot",
            "collections_compliance",
            "collections_conversation_intelligence",
            "collections_field_visit_planner",
            "collections_next_best_action",
            "collections_ptp_validation",
            "collections_recovery_strategy",
            "collections_settlement_negotiation",
            "guardrail_evaluator",
        }
        self.assertTrue(expected.issubset(prompt_ids))

        loaded = prompt_registry.load("collections_advisor")
        self.assertEqual(loaded.prompt_id, "collections_advisor")
        self.assertEqual(loaded.version, loaded.metadata["version"])
        self.assertIn("system.md", loaded.files_loaded)
        self.assertIn("developer.md", loaded.files_loaded)
        self.assertIn("few_shots.md", loaded.files_loaded)
        self.assertIn("output_schema.json", loaded.files_loaded)
        self.assertEqual(len(loaded.prompt_hash), 64)
        self.assertIn("Collections Advisor", loaded.text)
        self.assertIsNotNone(loaded.output_schema)

    def test_migrated_collection_agent_prompts_have_renderable_sections(self):
        for prompt_id in [
            "collections_behavioral_prediction",
            "collections_call_copilot",
            "collections_compliance",
            "collections_conversation_intelligence",
            "collections_field_visit_planner",
            "collections_next_best_action",
            "collections_ptp_validation",
            "collections_recovery_strategy",
            "collections_settlement_negotiation",
            "task_decomposer",
            "policy_assistant_system",
            "policy_assistant_retrieval_answer",
            "loan_eligibility_reasoning",
        ]:
            with self.subTest(prompt_id=prompt_id):
                loaded = prompt_registry.load(prompt_id)
                self.assertEqual(loaded.prompt_id, prompt_id)
                self.assertGreater(len(loaded.system.strip()), 100)
                self.assertGreater(len(loaded.developer.strip()), 50)
                self.assertEqual(len(loaded.prompt_hash), 64)
                self.assertIsNotNone(loaded.output_schema)

    def test_public_dict_hides_prompt_text_by_default(self):
        loaded = prompt_registry.load("intent_classifier")
        public = loaded.public_dict()
        debug = loaded.public_dict(include_text=True)
        self.assertNotIn("text", public)
        self.assertNotIn("sections", public)
        self.assertIn("prompt_hash", public)
        self.assertIn("text", debug)
        self.assertIn("sections", debug)

    def test_missing_required_file_fails_clearly(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "broken_prompt"
            folder.mkdir()
            (folder / "metadata.yaml").write_text(
                yaml.safe_dump({"prompt_id": "broken_prompt", "version": "v1"}),
                encoding="utf-8",
            )
            (folder / "system.md").write_text("System prompt", encoding="utf-8")
            registry = PromptRegistry(tmp)
            with self.assertRaises(PromptRegistryError) as ctx:
                registry.load("broken_prompt")
            self.assertIn("missing required file", str(ctx.exception))
            self.assertIn("developer.md", str(ctx.exception))

    def test_metadata_yaml_must_not_contain_prompt_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "bad_metadata"
            folder.mkdir()
            (folder / "metadata.yaml").write_text(
                yaml.safe_dump({"prompt_id": "bad_metadata", "version": "v1", "template": "do not store body here"}),
                encoding="utf-8",
            )
            (folder / "system.md").write_text("System prompt", encoding="utf-8")
            (folder / "developer.md").write_text("Developer prompt", encoding="utf-8")
            (folder / "few_shots.md").write_text("Examples", encoding="utf-8")
            (folder / "output_schema.json").write_text(json.dumps({"type": "object"}), encoding="utf-8")
            registry = PromptRegistry(tmp)
            with self.assertRaises(PromptRegistryError) as ctx:
                registry.load("bad_metadata")
            self.assertIn("must not contain prompt body", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
