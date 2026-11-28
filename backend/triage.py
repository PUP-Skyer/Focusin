# -*- coding: utf-8 -*-
"""智能分诊与日程时间提取（规则兜底版，无 LLM Key 时保证 Demo 可用）。"""
import re
import datetime
from email.header import decode_header, make_header

GROUPS = {"todo": "待办", "schedule": "日程", "notice": "通知",
           "important": "重要", "chatter": "闲聊"}

CN_WD = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}

RE_MONTHDAY = re.compile(
    r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]?\s*(上午|下午|晚上|中午|凌晨|早)?\s*"
    r"(\d{1,2})\s*[点时:：]\s*(\d{1,2})?分?")
RE_WEEKDAY = re.compile(
    r"(?:本周|这周|下周)?\s*周([一二三四五六日天])\s*(上午|下午|晚上|中午|凌晨|晚|早)?\s*"
    r"(\d{1,2})\s*[点时:：]\s*(\d{1,2})?分?")
RE_TOMORROW = re.compile(
    r"(明|后)天\s*(上午|下午|晚上|中午|晚|早)?\s*(\d{1,2})\s*[点时:：]\s*(\d{1,2})?分?")
RE_TONIGHT = re.compile(r"(今|明)晚\s*(\d{1,2})\s*[点时]\s*(\d{1,2})?分?")

TODO_KW = ["交", "提交", "发给", "报一下", "回复", "给一下", "记得", "别忘了",
           "截止", "下班前", "之前要", "需要你", "处理下", "买一下", "安排",
           "@我", "发我", "给我发", "确认一下", "准备", "完成"]
NOTICE_KW = ["通知", "公告", "放假", "调休", "考勤", "停水", "停电"]
IMPORTANT_KW = ["领导", "老板", "紧急", "重要", "客户", "家长会", "面试", "评审", "报销",
                "@所有人", "@全体", "@all", "@_all", "@_user_"]


def _hour(h, mer):
    if mer in ("下午", "晚上", "晚") and h < 12:
        h += 12
    if mer == "中午" and h < 11:
        h = 12
    return h


def parse_time(text, base=None):
    """从自然语言里解析明确日期时间；无明确日期则返回 None（防幻觉：不猜）。"""
    base = base or datetime.datetime.now()
    base = base.replace(second=0, microsecond=0)

    m = RE_MONTHDAY.search(text)
    if m:
        mon, day, mer, h, mi = m.groups()
        mon, day, h = int(mon), int(day), int(h)
        mi = int(mi) if mi else 0
        if 1 <= mon <= 12 and 1 <= day <= 31 and h <= 23 and mi <= 59:
            h = _hour(h, mer)
            try:
                dt = base.replace(month=mon, day=day, hour=h, minute=mi)
            except ValueError:
                return None
            if (dt - base).total_seconds() < -30 * 86400:
                dt = dt.replace(year=dt.year + 1)
            return dt

    m = RE_WEEKDAY.search(text)
    if m:
        wd, mer, h, mi = m.groups()
        h = int(h)
        mi = int(mi) if mi else 0
        if h <= 23 and mi <= 59:
            h = _hour(h, mer)
            if text[:m.start()].endswith("下周"):
                next_monday = base - datetime.timedelta(days=base.weekday()) \
                    + datetime.timedelta(days=7)
                return (next_monday + datetime.timedelta(days=CN_WD[wd])) \
                    .replace(hour=h, minute=mi)
            days = (CN_WD[wd] - base.weekday()) % 7
            return (base + datetime.timedelta(days=days)).replace(hour=h, minute=mi)

    m = RE_TOMORROW.search(text)
    if m:
        which, mer, h, mi = m.groups()
        h = int(h)
        mi = int(mi) if mi else 0
        if h <= 23 and mi <= 59:
            h = _hour(h, mer)
            d = base + datetime.timedelta(days=1 if which == "明" else 2)
            return d.replace(hour=h, minute=mi)

    m = RE_TONIGHT.search(text)
    if m:
        which, h, mi = m.groups()
        h, mi = int(h), int(mi or 0)
        if h <= 23 and mi <= 59:
            d = base if which == "今" else base + datetime.timedelta(days=1)
            return d.replace(hour=(h if h >= 12 else h + 12), minute=mi)
    return None


def classify(text, sender=""):
    t = text or ""
    if parse_time(t):
        return "schedule"
    if any(k in t for k in TODO_KW):
        return "todo"
    if any(k in t for k in NOTICE_KW):
        return "notice"
    if any(k in t for k in IMPORTANT_KW) or (len(t) >= 10 and any(
            k in (sender or "") for k in ("领导", "老板", "老师", "班主任"))):
        return "important"
    return "chatter"


def _clean_title_text(text):
    try:
        value = str(make_header(decode_header(str(text or ""))))
    except (LookupError, UnicodeError, ValueError):
        value = str(text or "")
    value = value.replace("\\n", " ").replace("\x00", "").replace("\\", "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"^\s*\{?\s*['\"]title['\"]\s*:\s*['\"]", "", value, flags=re.I)
    value = value.rstrip("\\ \t\r\n'\"}")
    return re.sub(r"\s+", " ", value).strip()


def event_title(text, limit=24):
    t = _clean_title_text(text)
    for drop in ("提醒一下：", "各位家长：", "【会议邀约】", "【通知】",
                 "提醒我", "帮我", "记得", "麻烦"):
        t = t.replace(drop, "")
    t = t.strip() or "未命名事项"
    return (t[:limit] + "…") if len(t) > limit else t
