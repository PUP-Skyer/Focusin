import datetime
import unittest
from unittest.mock import patch

from tests import support
import db
import ingest

support.init_db()


class IngestTests(unittest.TestCase):
    def setUp(self):
        db.reset()

    def test_duplicate_todo_is_ingested_only_once(self):
        args = ("feishu", "dept", "部门群", "同事", "2026-11-26 09:00",
                "请提交本周周报", "dup-todo")
        first = ingest.ingest(*args)
        second = ingest.ingest(*args)

        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(len(db.q("SELECT * FROM messages WHERE dedup_key=?", ("dup-todo",))), 1)
        self.assertEqual(len(db.q("SELECT * FROM todos WHERE source_msg_id=?", (first[0]["id"],))), 1)

    def test_schedule_message_creates_pending_event_with_source(self):
        with patch("ingest.triage.parse_time", return_value=datetime.datetime(2026, 11, 28, 15, 0)):
            message, group, event = ingest.ingest(
                "feishu", "dept", "部门群", "同事", "2026-11-26 09:00",
                "11月28日下午3点项目同步会", "schedule-1")

        self.assertEqual(group, "schedule")
        self.assertEqual(message["grp"], "schedule")
        self.assertEqual(event["title"], "11月28日下午3点项目同步会")
        self.assertEqual(event["start_at"], "2026-11-28 15:00")
        self.assertEqual(event["source_msg_id"], message["id"])
        self.assertEqual(event["status"], "pending")

    def test_duplicate_schedule_does_not_create_second_event(self):
        args = ("feishu", "dept", "部门群", "同事", "2026-11-26 09:00",
                "11月28日下午3点项目同步会", "dup-schedule")
        with patch("ingest.triage.parse_time", return_value=datetime.datetime(2026, 11, 28, 15, 0)):
            first = ingest.ingest(*args)
            second = ingest.ingest(*args)

        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(len(db.q("SELECT * FROM schedule_events")), 1)
        self.assertEqual(len(db.q("SELECT * FROM messages")), 1)


if __name__ == "__main__":
    unittest.main()
