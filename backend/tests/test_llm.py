import unittest
from unittest.mock import Mock, patch

import requests

from tests import support
import agent
import db
import llm

support.init_db()


class LLMTests(unittest.TestCase):
    def setUp(self):
        db.reset()

    def test_run_streams_text_and_accumulates_tool_call_fragments(self):
        db.set_setting("llm_base_url", "https://example.test/v1/")
        db.set_setting("llm_model", "demo-model")
        db.set_setting("llm_api_key", "test-key")
        response = Mock()
        response.iter_lines.return_value = [
            'data: {"choices":[{"delta":{"content":"你好"}}]}',
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call-1",'
            '"function":{"name":"search_","arguments":"{\\"query\\":"}}]}}]}',
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,'
            '"function":{"name":"messages","arguments":"\\"日程\\"}"}}]}}]}',
            'data: [DONE]',
        ]
        deltas = []
        with patch("llm.requests.post", return_value=response) as post:
            text, calls = llm.run(
                [{"role": "user", "content": "查日程"}],
                tools=[{"type": "function", "function": {"name": "search_messages"}}],
                on_delta=deltas.append,
            )

        self.assertEqual(text, "你好")
        self.assertEqual(deltas, ["你好"])
        self.assertEqual(calls, [{"id": "call-1", "name": "search_messages",
                                  "args": '{"query":"日程"}'}])
        post.assert_called_once()
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://example.test/v1/chat/completions")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-key")
        self.assertTrue(kwargs["json"]["stream"])
        self.assertEqual(kwargs["json"]["model"], "demo-model")
        self.assertEqual(len(kwargs["json"]["tools"]), 1)

    def test_llm_network_failure_falls_back_to_local_rules(self):
        events = []
        with patch("agent.llm.available", return_value=True), \
                patch("agent.llm.run", side_effect=requests.ConnectionError("offline")):
            agent._flow_sync("你好", events.append)

        self.assertTrue(any(event["type"] == "fallback" for event in events))
        self.assertFalse(any(event["type"] == "error" for event in events))
        done = next(event for event in events if event["type"] == "done")
        self.assertIn("没有直接命中", done["content"])
        assistant = db.q("SELECT content FROM chat_messages WHERE role='assistant' "
                         "ORDER BY id DESC LIMIT 1")[0]
        self.assertEqual(assistant["content"], done["content"])

    def test_llm_http_error_discards_partial_output_and_falls_back(self):
        events = []

        def fail(_messages, tools=None, on_delta=None):
            on_delta("半截回答")
            raise requests.HTTPError("401 invalid key")

        with patch("agent.llm.available", return_value=True), \
                patch("agent.llm.run", side_effect=fail):
            agent._flow_sync("你好", events.append)

        done = next(event for event in events if event["type"] == "done")
        self.assertNotIn("半截回答", done["content"])
        self.assertIn("没有直接命中", done["content"])
        self.assertTrue(any(event["type"] == "fallback" for event in events))

    def test_available_requires_base_url_model_and_key(self):
        self.assertFalse(llm.available())
        db.set_setting("llm_base_url", "https://example.test/v1")
        db.set_setting("llm_model", "demo-model")
        self.assertFalse(llm.available())
        db.set_setting("llm_api_key", "test-key")
        self.assertTrue(llm.available())


if __name__ == "__main__":
    unittest.main()
