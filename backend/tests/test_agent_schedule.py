import threading
import time
import unittest
from unittest.mock import patch

from tests import support
import agent
import db

support.init_db()


class ScheduleApprovalTests(unittest.TestCase):
    def setUp(self):
        db.reset()

    def _resolve_approval(self, decision):
        events = []
        outcome = {}

        def run():
            try:
                outcome["result"] = agent.execute_tool(
                    "create_schedule",
                    {"title": "项目评审", "start_at": "2026-11-27 15:00"},
                    events.append,
                )
            except Exception as exc:  # surfaced in the main test thread
                outcome["error"] = exc

        thread = threading.Thread(target=run)
        thread.start()
        approval = None
        deadline = time.time() + 2
        while time.time() < deadline:
            rows = db.q("SELECT * FROM approvals WHERE status='pending' ORDER BY id DESC")
            if rows:
                approval = rows[0]
                break
            time.sleep(0.01)

        self.assertIsNotNone(approval)
        self.assertEqual(db.q("SELECT * FROM schedule_events"), [])
        db.ex("UPDATE approvals SET status=?, decision=?, decided_at=? WHERE id=?",
              ("approved" if decision == "approve" else "denied", decision,
               db.now_iso(), approval["id"]))
        thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertNotIn("error", outcome)
        return outcome["result"], events, approval["id"]

    def test_approval_must_happen_before_schedule_is_created(self):
        result, events, approval_id = self._resolve_approval("approve")

        self.assertTrue(result["ok"])
        self.assertEqual([event["type"] for event in events
                          if event["type"].startswith("approval")],
                         ["approval", "approval_resolved"])
        rows = db.q("SELECT * FROM schedule_events")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "confirmed")
        audit = db.q("SELECT * FROM audit_log ORDER BY id DESC")
        self.assertEqual(audit[0]["tool"], "create_schedule")
        self.assertEqual(audit[0]["risk"], "moderate")
        self.assertEqual(audit[0]["approval_id"], approval_id)

    def test_denied_schedule_is_not_created_and_rejection_is_audited(self):
        result, events, approval_id = self._resolve_approval("deny")

        self.assertFalse(result["ok"])
        self.assertIn("拒绝", result["reason"])
        self.assertEqual(db.q("SELECT * FROM schedule_events"), [])
        audit = db.q("SELECT * FROM audit_log ORDER BY id DESC")[0]
        self.assertEqual(audit["approval_id"], approval_id)
        self.assertIn("拒绝", audit["result"])

    def test_timed_out_schedule_is_not_created_and_timeout_is_audited(self):
        events = []
        with patch("agent.time.time", side_effect=[0, 0, 121]), \
                patch("agent.time.sleep", return_value=None):
            result = agent.execute_tool(
                "create_schedule",
                {"title": "项目评审", "start_at": "2026-11-27 15:00"},
                events.append,
            )

        self.assertFalse(result["ok"])
        self.assertIn("超时", result["reason"])
        self.assertEqual(db.q("SELECT * FROM schedule_events"), [])
        approval = db.q("SELECT * FROM approvals ORDER BY id DESC")[0]
        self.assertEqual(approval["status"], "timeout")
        self.assertEqual(approval["decision"], "deny")
        audit = db.q("SELECT * FROM audit_log ORDER BY id DESC")[0]
        self.assertEqual(audit["approval_id"], approval["id"])
        self.assertIn("超时", audit["result"])

    def test_empty_title_is_rejected_without_creating_schedule(self):
        result = agent.t_create_schedule({"title": "   ", "start_at": "2026-11-27 15:00"})

        self.assertFalse(result["ok"])
        self.assertIn("格式不合法", result["reason"])
        self.assertEqual(db.q("SELECT * FROM schedule_events"), [])

    def test_time_with_trailing_characters_is_rejected(self):
        result = agent.t_create_schedule({"title": "项目评审", "start_at": "2026-11-27 15:00abc"})

        self.assertFalse(result["ok"])
        self.assertEqual(db.q("SELECT * FROM schedule_events"), [])

    def test_invalid_calendar_date_is_rejected_without_creating_schedule(self):
        result = agent.t_create_schedule({"title": "项目评审", "start_at": "2026-11-99 15:00"})

        self.assertFalse(result["ok"])
        self.assertIn("格式不合法", result["reason"])
        self.assertEqual(db.q("SELECT * FROM schedule_events"), [])

    def test_invalid_time_is_rejected_without_creating_schedule(self):
        result = agent.t_create_schedule({"title": "项目评审", "start_at": "周五下午3点"})

        self.assertFalse(result["ok"])
        self.assertIn("格式不合法", result["reason"])
        self.assertEqual(db.q("SELECT * FROM schedule_events"), [])


if __name__ == "__main__":
    unittest.main()
