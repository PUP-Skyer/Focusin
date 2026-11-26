# -*- coding: utf-8 -*-
"""LLM 网关：OpenAI 兼容 API，流式输出；未配置 Key 时返回不可用，Agent 走规则兜底。"""
import json

import requests
import db


def config():
    return {
        "base_url": db.get_setting("llm_base_url", ""),
        "api_key": db.get_setting("llm_api_key", ""),
        "model": db.get_setting("llm_model", ""),
    }


def available():
    c = config()
    return bool(c["base_url"] and c["api_key"] and c["model"])


def run(messages, tools=None, on_delta=None):
    """一次对话调用，流式转发文本增量，返回 (最终文本, 工具调用列表)。"""
    c = config()
    payload = {"model": c["model"], "messages": messages, "stream": True}
    if tools:
        payload["tools"] = tools
    resp = requests.post(
        c["base_url"].rstrip("/") + "/chat/completions",
        headers={"Authorization": f"Bearer {c['api_key']}"},
        json=payload, stream=True, timeout=(15, 300))
    resp.raise_for_status()

    text_parts, tool_acc = [], {}

    for raw in resp.iter_lines(decode_unicode=True):
        if not raw or not raw.startswith("data:"):
            continue
        data = raw[5:].strip()
        if data == "[DONE]":
            break
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue
        delta = chunk["choices"][0].get("delta", {}) if chunk.get("choices") else {}
        if delta.get("content"):
            text_parts.append(delta["content"])
            if on_delta:
                on_delta(delta["content"])
        for tc in delta.get("tool_calls") or []:
            idx = tc.get("index", 0)
            slot = tool_acc.setdefault(idx, {"id": None, "name": "", "args": ""})
            if tc.get("id"):
                slot["id"] = tc["id"]
            if tc.get("function", {}).get("name"):
                slot["name"] += tc["function"]["name"]
            if tc.get("function", {}).get("arguments"):
                slot["args"] += tc["function"]["arguments"]

    tool_calls = [t for t in tool_acc.values() if t["name"]]
    return "".join(text_parts), tool_calls
