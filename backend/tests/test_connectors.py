import unittest
from unittest.mock import patch

from tests import support
import connectors
import db

support.init_db()


class FakeConnector:
    def __init__(self):
        self.calls = []

    def fetch_conversation(self, creds, conv_key, conv_title):
        self.calls.append(conv_key)
        return [{
            "sender": "同事",
            "ts": "2026-11-26 09:00",
            "text": "请提交本周周报",
            "dedup": f"fake:{conv_key}:1",
        }]


class ConnectorSyncTests(unittest.TestCase):
    def setUp(self):
        db.reset()

    def test_sync_requests_only_allowlisted_active_conversations(self):
        fake = FakeConnector()
        connectors.save_credentials("email", {
            "host": "imap.example.com",
            "port": "993",
            "username": "demo@example.com",
            "password": "not-a-real-secret",
        })
        db.ex("INSERT INTO subscriptions(channel_key, conv_key, conv_title, active, added_at) "
              "VALUES(?,?,?,?,?)", ("email", "allowed", "允许的会话", 1, "2026-11-26 09:00"))
        db.ex("INSERT INTO subscriptions(channel_key, conv_key, conv_title, active, added_at) "
              "VALUES(?,?,?,?,?)", ("email", "blocked", "未允许的会话", 0, "2026-11-26 09:00"))

        with patch.dict(connectors.CATALOG["email"], {"module": fake}):
            result = connectors.sync("email")

        self.assertTrue(result["ok"])
        self.assertEqual(result["fetched"], 1)
        self.assertEqual(result["new"], 1)
        self.assertEqual(result["subscriptions"], 1)
        self.assertEqual(fake.calls, ["allowed"])
        rows = db.q("SELECT * FROM messages")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["conv_key"], "allowed")
        self.assertEqual(rows[0]["grp"], "todo")
        self.assertEqual(len(db.q("SELECT * FROM todos")), 1)


if __name__ == "__main__":
    unittest.main()
