import unittest

from tests import support
import agent
import db

support.init_db()


class SearchMessageTests(unittest.TestCase):
    def setUp(self):
        db.reset()

    def test_no_hit_returns_explicit_no_match(self):
        db.ex("INSERT INTO messages(channel_key, conv_key, conv_title, sender, ts, text, grp, dedup_key, created_at) "
              "VALUES(?,?,?,?,?,?,?,?,?)",
              ("feishu", "dept", "飞书 · 部门群｜产品研发部", "李经理(领导)",
               "2026-11-26 09:00", "报销新流程：4 月起发票要先在系统里拍照上传。",
               "important", "hit-1", "2026-11-26 09:00"))

        result = agent.t_search_messages({"query": "量子纠缠"})

        self.assertEqual(result, "（没有找到相关消息）")

    def test_hit_returns_original_message_with_full_citation(self):
        db.ex("INSERT INTO messages(channel_key, conv_key, conv_title, sender, ts, text, grp, dedup_key, created_at) "
              "VALUES(?,?,?,?,?,?,?,?,?)",
              ("feishu", "dept", "飞书 · 部门群｜产品研发部", "李经理(领导)",
               "2026-11-25 16:44", "报销新流程：4 月起发票要先在系统里拍照上传，纸质单据周四前交财务。",
               "important", "hit-2", "2026-11-25 16:44"))

        result = agent.t_search_messages({"query": "领导上周关于报销说了什么"})

        self.assertIn("报销新流程：4 月起发票要先在系统里拍照上传，纸质单据周四前交财务。", result)
        self.assertIn("飞书 · 部门群｜产品研发部", result)
        self.assertIn("李经理(领导)", result)
        self.assertIn("2026-11-25 16:44", result)
        self.assertIn("消息#1", result)

    def test_chatter_is_excluded_from_search_results(self):
        db.ex("INSERT INTO messages(channel_key, conv_key, conv_title, sender, ts, text, grp, dedup_key, created_at) "
              "VALUES(?,?,?,?,?,?,?,?,?)",
              ("wechat", "family", "微信 · 家人群", "妈妈",
               "2026-11-26 08:00", "彩虹独角兽是真的存在的", "chatter", "chatter-1", "2026-11-26 08:00"))

        result = agent.t_search_messages({"query": "彩虹独角兽"})

        self.assertEqual(result, "（没有找到相关消息）")

    def test_fallback_flow_no_hit_gives_followup_examples_without_fabrication(self):
        db.ex("INSERT INTO messages(channel_key, conv_key, conv_title, sender, ts, text, grp, dedup_key, created_at) "
              "VALUES(?,?,?,?,?,?,?,?,?)",
              ("feishu", "dept", "飞书 · 部门群｜产品研发部", "李经理(领导)",
               "2026-11-26 09:00", "报销新流程：4 月起发票要先在系统里拍照上传。",
               "important", "hit-3", "2026-11-26 09:00"))

        events = list(agent.flow("量子纠缠"))
        answer = next(ev["content"] for ev in events if ev.get("type") == "done")

        self.assertIn("没有直接命中", answer)
        self.assertIn("查日程", answer)
        self.assertIn("检索历史消息", answer)
        self.assertNotIn("报销新流程", answer)

    def test_search_tool_is_safe_and_audited(self):
        db.ex("INSERT INTO messages(channel_key, conv_key, conv_title, sender, ts, text, grp, dedup_key, created_at) "
              "VALUES(?,?,?,?,?,?,?,?,?)",
              ("feishu", "dept", "飞书 · 部门群｜产品研发部", "李经理(领导)",
               "2026-11-25 16:44", "报销新流程：4 月起发票要先在系统里拍照上传。",
               "important", "hit-4", "2026-11-25 16:44"))
        events = []

        result = agent.execute_tool("search_messages", {"query": "报销"}, events.append)

        self.assertIn("报销新流程", result)
        self.assertFalse(any(ev.get("type") == "approval" for ev in events))
        self.assertEqual(events[0]["risk"], "safe")
        audit = db.q("SELECT * FROM audit_log ORDER BY id DESC LIMIT 1")[0]
        self.assertEqual(audit["tool"], "search_messages")
        self.assertEqual(audit["risk"], "safe")
        self.assertIn('"query": "报销"', audit["args"])
        self.assertIn("报销新流程", audit["result"])

    def test_fallback_flow_hit_answer_uses_original_citation(self):
        original = "报销新流程：4 月起发票要先在系统里拍照上传，纸质单据周四前交财务。"
        db.ex("INSERT INTO messages(channel_key, conv_key, conv_title, sender, ts, text, grp, dedup_key, created_at) "
              "VALUES(?,?,?,?,?,?,?,?,?)",
              ("feishu", "dept", "飞书 · 部门群｜产品研发部", "李经理(领导)",
               "2026-11-25 16:44", original, "important", "hit-5", "2026-11-25 16:44"))

        events = list(agent.flow("领导上周关于报销说了什么"))
        answer = next(ev["content"] for ev in events if ev.get("type") == "done")

        self.assertIn(original, answer)
        self.assertIn("飞书 · 部门群｜产品研发部", answer)
        self.assertIn("李经理(领导)", answer)
        self.assertIn("2026-11-25 16:44", answer)
        self.assertNotIn("没有直接命中", answer)


if __name__ == "__main__":
    unittest.main()
