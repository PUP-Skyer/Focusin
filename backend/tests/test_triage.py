import datetime
import unittest

import triage


class TriageTests(unittest.TestCase):
    def test_todo_keyword_is_classified_as_todo(self):
        self.assertEqual(triage.classify("请提交本周周报"), "todo")

    def test_notice_keyword_is_classified_as_notice(self):
        self.assertEqual(triage.classify("通知：本周五下午放假"), "notice")

    def test_important_keyword_is_classified_as_important(self):
        self.assertEqual(triage.classify("客户投诉需要紧急处理"), "important")

    def test_plain_message_is_classified_as_chatter(self):
        self.assertEqual(triage.classify("中午吃什么"), "chatter")

    def test_explicit_time_is_parsed_and_classified_as_schedule(self):
        base = datetime.datetime(2026, 11, 26, 9, 0)
        parsed = triage.parse_time("明天下午3点项目同步会", base=base)

        self.assertEqual(parsed, datetime.datetime(2026, 11, 27, 15, 0))
        self.assertEqual(triage.classify("明天下午3点项目同步会"), "schedule")


if __name__ == "__main__":
    unittest.main()
