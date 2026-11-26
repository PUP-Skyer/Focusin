# -*- coding: utf-8 -*-
"""演示数据集：8 群 × 200+ 条消息（待办/日程/通知/重要/闲聊混合）。
时间以“今天”为基准动态生成，保证任何一天打开 Demo 数据都是新鲜的。"""
import random
import datetime
from contextlib import closing

import db
import triage

CHANNELS = [
    ("wechat", "微信", "local", "本地化只读 · 实验性"),
    ("feishu", "飞书", "official", "官方 API"),
    ("dingtalk", "钉钉", "official", "官方 API"),
    ("email", "邮箱", "imap", "IMAP 水位增量"),
    ("qq", "QQ", "local", "本地化只读 · 实验性"),
]

# (channel, conv_key, title, 成员名单)
CONVS = [
    ("feishu", "dept", "飞书 · 部门群｜产品研发部", ["李经理(领导)", "产品-阿May", "前端-大山", "人事-S姐"]),
    ("feishu", "proj", "飞书 · 项目群｜聚光官网改版", ["产品-阿May", "前端-大山", "设计-老白"]),
    ("wechat", "client", "微信 · 客户群｜星辰传媒", ["星辰传媒-王姐", "星辰-小刘"]),
    ("wechat", "family", "微信 · 家人群", ["妈妈", "班主任-刘老师", "爸爸"]),
    ("wechat", "proj", "微信 · 项目群｜改稿冲刺", ["老板-峰哥", "设计师-小周"]),
    ("dingtalk", "admin", "钉钉 · 行政通知群", ["行政-小赵", "前台-婷婷"]),
    ("email", "inbox", "邮箱 · 收件箱", ["发件人"]),
    ("qq", "industry", "QQ · 行业交流群", ["群友-老K", "群友-麦子", "群友-阿飞"]),
]

# 剧本消息：分诊管道的关键样例 (channel, conv, sender, 天偏移, 时, 分, 文本)
SCRIPTED = [
    ("feishu", "dept", "李经理(领导)", 0, 9, 12, "提醒一下：周四晚 7 点例会，别迟到，会议室 A503，带上周报。"),
    ("wechat", "client", "星辰传媒-王姐", 0, 9, 40, "明早十点前给我发 v2 方案哈，客户等着一版看排版。"),
    ("email", "inbox", "星辰传媒 项目对接", 0, 10, 5, "【会议邀约】本周五 15:00 项目评审会，地点：腾讯会议 882-116-772，请准时参加。"),
    ("wechat", "family", "班主任-刘老师", 0, 12, 30, "各位家长：明天晚上 7 点孩子家长会，要求家长都到，地点学校报告厅。"),
    ("wechat", "proj", "设计师-小周", 0, 11, 21, "@我 logo 第二版今天下班前给一下，客户等着看。"),
    ("feishu", "dept", "李经理(领导)", -1, 16, 44, "报销新流程：4 月起发票要先在系统里拍照上传，纸质单据周四前交财务，别再直接拿给我。"),
    ("dingtalk", "admin", "行政-小赵", 0, 10, 2, "【通知】下周一放假调休，本周六上班，考勤正常打卡。"),
    ("wechat", "client", "星辰传媒-王姐", -1, 15, 20, "预算确认了，这轮先做两套方向，报价单明早发我邮箱。"),
    ("feishu", "proj", "产品-阿May", -1, 14, 8, "聚光官网改版评审并到周四晚 7 点例会一起过，材料我出，你们把首页稿改完。"),
    ("qq", "industry", "群友-老K", 0, 13, 5, "最近 AI 应用层的流量真起来了，消息聚合类工具你觉得有戏吗？"),
    ("wechat", "family", "妈妈", 0, 8, 0, "降压药吃完了，今晚买一下，别忘。"),
    ("email", "inbox", "智联招聘", -1, 9, 33, "您的简历已被查看。面试时间：11 月 28 日 上午 10 点，请提前 15 分钟到。"),
    ("feishu", "dept", "人事-S姐", -1, 18, 2, "下季度 OKR 周三下班前交，格式见共享文档，逾期抄送领导。"),
    ("wechat", "proj", "老板-峰哥", -2, 21, 10, "改稿别死磕，先出 70 分版本快速验证，明早我要看。"),
    ("dingtalk", "admin", "行政-小赵", -3, 11, 0, "【公告】本月消防检查，工位杂物记得清一下。"),
    ("qq", "industry", "群友-麦子", -2, 20, 15, "分享：2026 消息聚合工具横评 https://example.com/review"),
]

FILLERS = [
    "哈哈哈哈", "收到", "牛", "+1", "表情包", "中午吃啥", "已看完，确实",
    "蹲一个后续", "沙发", "谢谢分享", "马上", "OK", "了解一下",
    "这也太卷了", "羡慕", "下午茶走起", "666", "刚看到", "在忙，稍后回",
    "晚安", "早上好", "冲鸭", "今晚有球赛", "帮顶", "学习了", "确实",
    "笑死", "有内味了", "顶", "然后呢", "马克", "链接先存了",
]


def seed():
    db.reset()
    rng = random.Random(20261126)
    now = datetime.datetime.now()
    rows = []

    def add(channel, conv, title, sender, dt, text):
        dedup = f"seed:{channel}:{conv}:{dt.strftime('%Y%m%d%H%M')}:{sender}:{text[:12]}"
        rows.append((channel, conv, title, sender,
                    dt.strftime("%Y-%m-%d %H:%M"), text, dedup, db.now_iso()))

    conv_title = {ck: title for _, ck, title, _ in CONVS}

    for ch, ck, sender, day_off, hh, mm, text in SCRIPTED:
        dt = (now + datetime.timedelta(days=day_off)).replace(
            hour=hh, minute=mm, second=0, microsecond=0)
        if day_off == 0 and dt > now:  # 今日消息必须已发生
            dt = now - datetime.timedelta(minutes=rng.randint(3, 30))
        add(ch, ck, conv_title[ck], sender, dt, text)

    for day_off in range(-6, 1):
        n = rng.randint(26, 34) if day_off == 0 else rng.randint(22, 30)
        for _ in range(n):
            ch, ck, title, members = rng.choice(CONVS)
            sender = rng.choice(members)
            dt = (now + datetime.timedelta(days=day_off)).replace(
                hour=rng.randint(8, 22), minute=rng.randint(0, 59),
                second=0, microsecond=0)
            if day_off == 0 and dt > now:
                dt = now - datetime.timedelta(minutes=rng.randint(1, 90))
            add(ch, ck, title, sender, dt, rng.choice(FILLERS))

    with closing(db.get_conn()) as c:
        for key, name, typ, _ in CHANNELS:
            c.execute("INSERT OR REPLACE INTO channels(key,name,type,status) "
                      "VALUES(?,?,?,'on')", (key, name, typ))
        c.executemany(
            "INSERT OR IGNORE INTO messages(channel_key,conv_key,conv_title,"
            "sender,ts,text,dedup_key,created_at) VALUES(?,?,?,?,?,?,?,?)", rows)
        c.commit()

    triage_all()
    stats = db.q("SELECT grp, COUNT(*) n FROM messages GROUP BY grp")
    return {r["grp"] or "未分诊": r["n"] for r in stats}


def triage_all():
    """分诊管道：五分组 + 待办入库 + 待确认日程（带原文依据）。"""
    for m in db.q("SELECT id, text, sender FROM messages WHERE grp='' OR grp IS NULL"):
        grp = triage.classify(m["text"], m["sender"])
        db.ex("UPDATE messages SET grp=? WHERE id=?", (grp, m["id"]))
        if grp == "todo":
            db.ex("INSERT OR IGNORE INTO todos(text, source_msg_id, created_at) "
                  "VALUES(?,?,?)", (triage.event_title(m["text"]), m["id"], db.now_iso()))
        elif grp == "schedule":
            dt = triage.parse_time(m["text"])
            if dt:
                db.ex("INSERT OR IGNORE INTO schedule_events(title, start_at, "
                      "source_msg_id, status, dedup_key, created_at) "
                      "VALUES(?,?,?,?,?,?)",
                      (triage.event_title(m["text"]), dt.strftime("%Y-%m-%d %H:%M"),
                       m["id"], "pending", f"msg:{m['id']}", db.now_iso()))
