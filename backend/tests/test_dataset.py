import unittest

from tests import support
import dataset
import db

support.init_db()


class DatasetTests(unittest.TestCase):
    def setUp(self):
        db.reset()

    def test_reseed_produces_repeatable_demo_dataset(self):
        dataset.seed()
        first_messages = db.q("SELECT text, COUNT(*) n FROM messages "
                              "GROUP BY text ORDER BY text")
        first_groups = db.q("SELECT grp, COUNT(*) n FROM messages "
                            "GROUP BY grp ORDER BY grp")
        first_schedules = db.q("SELECT COUNT(*) n FROM schedule_events")[0]["n"]
        first_todos = db.q("SELECT COUNT(*) n FROM todos")[0]["n"]

        dataset.seed()
        second_messages = db.q("SELECT text, COUNT(*) n FROM messages "
                               "GROUP BY text ORDER BY text")
        second_groups = db.q("SELECT grp, COUNT(*) n FROM messages "
                             "GROUP BY grp ORDER BY grp")
        second_schedules = db.q("SELECT COUNT(*) n FROM schedule_events")[0]["n"]
        second_todos = db.q("SELECT COUNT(*) n FROM todos")[0]["n"]

        self.assertEqual(second_messages, first_messages)
        self.assertEqual(second_groups, first_groups)
        self.assertEqual(second_schedules, first_schedules)
        self.assertEqual(second_todos, first_todos)

    def test_reseed_removes_runtime_changes(self):
        dataset.seed()
        db.ex("INSERT INTO messages(channel_key,conv_key,conv_title,sender,ts,text,"
              "dedup_key,created_at) VALUES(?,?,?,?,?,?,?,?)",
              ("feishu", "dept", "临时会话", "我", db.now_iso(), "临时消息",
               "temporary", db.now_iso()))
        db.ex("INSERT INTO approvals(tool,args,risk,status,created_at) "
              "VALUES(?,?,?,?,?)", ("create_schedule", "{}", "moderate",
                                    "pending", db.now_iso()))

        dataset.seed()

        self.assertEqual(db.q("SELECT * FROM messages WHERE dedup_key='temporary'"), [])
        self.assertEqual(db.q("SELECT * FROM approvals"), [])


if __name__ == "__main__":
    unittest.main()
