#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_records.py —— 微信聊天记录包 → 结构化记录表

输入：WorkBuddy 微信分享入口落盘的 聊天记录.txt（或其所在目录）
输出：<out-dir>/records.jsonl  一行一条记录
      <out-dir>/records.csv    Excel 可直接打开（utf-8-sig）
      <out-dir>/parse_report.txt  解析报告

用法：
  python3 build_records.py <path> [--out-dir DIR] [--source chat|favorite|moments|official]
                          [--chat-name 名称] [--batch-id ID] [--stats]

特性：
  * 纯标准库，无第三方依赖
  * 按 hash_dup 与既有 records.jsonl 自动合并去重
  * 时间解析兼容 "2026年10月29日 12:52" / "2026-10-29 12:52" / "2026/10/29 12:52"
  * 消息类型从 [图片] [语音] [视频] [表情] [文件] [链接] [小程序] 等占位符推断
"""

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from datetime import datetime

# ---------------------------------------------------------------- 时间解析

INLINE_PATTERNS = [
    # 2026年10月29日 12:52
    re.compile(r"^(\d{4})年(\d{1,2})月(\d{1,2})日\s+(\d{1,2}):(\d{2})(?::(\d{2}))?$"),
    # 2026-10-29 12:52  /  2026/10/29 12:52
    re.compile(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?$"),
    # 2026年10月29日 下午3:05
    re.compile(r"^(\d{4})年(\d{1,2})月(\d{1,2})日\s*(上午|下午|晚上|凌晨|中午)?\s*(\d{1,2}):(\d{2})$"),
]

# 同一行内 "张三 2026年10月29日 12:52" 形式（部分导出格式）
SAME_LINE = re.compile(
    r"^(?P<sender>\S.{0,40}?)\s+(?P<ts>\d{4}(?:年|-|/)\d{1,2}(?:月|-|/)\d{1,2}日?\s*\S{0,2}\d{1,2}:\d{2}(?::\d{2})?)$"
)


def parse_ts(line):
    """把一行时间文本解析成 datetime，失败返回 None。"""
    s = line.strip()
    for idx, pat in enumerate(INLINE_PATTERNS):
        m = pat.match(s)
        if not m:
            continue
        g = m.groups()
        if idx == 2:
            y, mo, d, cn, h, mi = g
            h = int(h)
            if cn in ("下午", "晚上") and h < 12:
                h += 12
            if cn == "中午" and h < 11:
                h += 12
            if cn == "凌晨" and h == 12:
                h = 0
            try:
                return datetime(int(y), int(mo), int(d), h, int(mi))
            except ValueError:
                return None
        y, mo, d, h, mi = g[0], g[1], g[2], g[3], g[4]
        sec = g[5] if len(g) > 5 and g[5] else 0
        try:
            return datetime(int(y), int(mo), int(d), int(h), int(mi), int(sec))
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------- 类型推断

MARKERS = [
    ("[图片]", "image"), ("[照片]", "image"), ("<image>", "image"), ("[相册]", "image"),
    ("[语音]", "voice"), ("[音频]", "voice"), ("[voice]", "voice"),
    ("[视频]", "video"), ("<video>", "video"),
    ("[动画表情]", "sticker"), ("[表情]", "sticker"), ("[emoji]", "sticker"),
    ("[文件]", "file"), ("[文档]", "file"),
    ("[链接]", "link"), ("[网页]", "link"),
    ("[小程序]", "miniapp"), ("[公众号]", "official"),
    ("[红包]", "redpacket"), ("[转账]", "transfer"),
    ("[位置]", "location"), ("[名片]", "contact"), ("[接龙]", "chain"),
]

EMOJI_TAG = re.compile(r"\[[\u4e00-\u9fa5]{1,6}\]")


def infer_type(content):
    """从折叠占位符 / 链接推断消息类型。"""
    hits = {t for k, t in MARKERS if k in content}
    if not hits:
        if re.search(r"https?://\S+", content):
            return "link"
        return "text"
    if len(hits) == 1:
        return hits.pop()
    return "mixed"


MEDIA_TOKENS = {k for k, _ in MARKERS}


def emoji_tags(content):
    """抽出 [送心] 这类情绪表情标签；排除 [图片]/[语音] 等媒体占位符。"""
    tags = set(EMOJI_TAG.findall(content)) - MEDIA_TOKENS
    return "|".join(sorted(tags))


# ---------------------------------------------------------------- 解析主逻辑

def read_text(path):
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def parse_file(path):
    """返回 [{'sender','ts','content','raw_lines'}]"""
    raw = read_text(path)
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    # 1) 找出所有 "发送人行"：其后一行是时间；或本行自带时间
    header = []  # (idx, sender, ts_line_idx or None, ts)
    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        ts = parse_ts(s)
        if ts:
            continue  # 纯时间行，由上一行认领
        # 同行形式
        m = SAME_LINE.match(s)
        if m and parse_ts(m.group("ts")):
            header.append((i, m.group("sender").strip(), i, parse_ts(m.group("ts"))))
            continue
        # 下一行是时间 → 本行为发送人
        if i + 1 < len(lines):
            nxt = parse_ts(lines[i + 1].strip())
            if nxt is not None:
                header.append((i, s, i + 1, nxt))

    msgs = []
    for k, (idx, sender, ts_idx, ts) in enumerate(header):
        start = ts_idx + 1
        end = header[k + 1][0] if k + 1 < len(header) else len(lines)
        body = lines[start:end]
        # 去掉尾部空行
        while body and not body[-1].strip():
            body.pop()
        while body and not body[0].strip():
            body.pop(0)
        content = "\n".join(ln.rstrip() for ln in body).strip()
        msgs.append({"sender": sender, "ts": ts, "content": content})
    return msgs


# ---------------------------------------------------------------- 记录装配

def build_record(msg, ctx, seq):
    content = msg["content"]
    ts = msg["ts"]
    digest = hashlib.sha1(
        f"{ctx['batch_id']}|{msg['sender']}|{ts.isoformat()}|{content}".encode("utf-8")
    ).hexdigest()[:16]
    rec = {
        "record_id": f"{ctx['batch_id']}-{seq:04d}",
        "batch_id": ctx["batch_id"],
        "source_type": ctx["source"],
        "chat_name": ctx["chat_name"],
        "sender": msg["sender"],
        "is_self": "",
        "msg_time": ts.strftime("%Y-%m-%d %H:%M:%S"),
        "msg_date": ts.strftime("%Y-%m-%d"),
        "msg_hour": ts.hour,
        "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][ts.weekday()],
        "msg_type": infer_type(content),
        "content_raw": content,
        "content_clean": re.sub(r"[ \t]{2,}", " ", content).strip(),
        "char_len": len(content),
        "emoji_tags": emoji_tags(content),
        "media_path": "",
        "media_desc": "",
        "thread_id": ts.strftime("%Y-%m-%d"),
        "topic_tags": "",
        "emotion": "",
        "sentiment_score": "",
        "entities_people": "",
        "entities_place": "",
        "action_item": "",
        "importance": "",
        "mode": ctx["mode"],
        "privacy_level": "normal",
        "confidence": "high",
        "hash_dup": digest,
        "kb_url": "",
        "ingested_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    return rec


CSV_FIELDS = [
    "record_id", "batch_id", "source_type", "chat_name", "sender", "is_self",
    "msg_time", "msg_date", "msg_hour", "weekday", "msg_type",
    "content_raw", "content_clean", "char_len", "emoji_tags",
    "media_path", "media_desc", "thread_id", "topic_tags",
    "emotion", "sentiment_score", "entities_people", "entities_place",
    "action_item", "importance", "mode", "privacy_level", "confidence",
    "hash_dup", "kb_url", "ingested_at",
]


def load_existing(jsonl_path):
    rows = []
    if os.path.exists(jsonl_path):
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return rows


def main():
    ap = argparse.ArgumentParser(description="微信聊天记录包 → 结构化记录表")
    ap.add_argument("path", help="聊天记录.txt 或其所在目录")
    ap.add_argument("--out-dir", default="kb", help="输出目录，默认 ./kb")
    ap.add_argument("--source", default="chat",
                    choices=["chat", "favorite", "moments", "official", "mixed"],
                    help="来源类型")
    ap.add_argument("--chat-name", default="", help="会话名 / 群名")
    ap.add_argument("--batch-id", default="", help="批次号，默认按目录名或时间生成")
    ap.add_argument("--mode", default="M01", help="场景模式编号，默认 M01 冷存档")
    ap.add_argument("--no-merge", action="store_true", help="不合并既有 records.jsonl")
    ap.add_argument("--stats", action="store_true", help="只打印统计，不写文件")
    args = ap.parse_args()

    target = args.path
    if os.path.isdir(target):
        cand = os.path.join(target, "聊天记录.txt")
        if os.path.exists(cand):
            target = cand
        else:
            txts = [f for f in os.listdir(target) if f.lower().endswith(".txt")]
            if not txts:
                sys.exit(f"[x] 目录中未找到 聊天记录.txt：{args.path}")
            target = os.path.join(target, sorted(txts)[0])

    if not os.path.exists(target):
        sys.exit(f"[x] 文件不存在：{target}")

    msgs = parse_file(target)
    if not msgs:
        sys.exit("[x] 未解析出任何消息，请检查文件格式是否为「发送人 / 时间 / 内容」三行式")

    batch_id = args.batch_id
    if not batch_id:
        stamp = msgs[0]["ts"].strftime("%Y%m%d_%H%M")
        batch_id = f"wch-{stamp}"

    ctx = {"batch_id": batch_id, "source": args.source,
           "chat_name": args.chat_name, "mode": args.mode}

    new_rows = [build_record(m, ctx, i + 1) for i, m in enumerate(msgs)]

    os.makedirs(args.out_dir, exist_ok=True)
    jsonl_path = os.path.join(args.out_dir, "records.jsonl")
    csv_path = os.path.join(args.out_dir, "records.csv")
    report_path = os.path.join(args.out_dir, "parse_report.txt")

    existing = [] if args.no_merge else load_existing(jsonl_path)
    seen = {r.get("hash_dup") for r in existing if r.get("hash_dup")}
    added = [r for r in new_rows if r["hash_dup"] not in seen]
    skipped = len(new_rows) - len(added)
    all_rows = existing + added
    all_rows.sort(key=lambda r: (r.get("msg_time", ""), r.get("record_id", "")))

    # ---- 统计
    senders = {}
    types = {}
    for r in new_rows:
        senders[r["sender"]] = senders.get(r["sender"], 0) + 1
        types[r["msg_type"]] = types.get(r["msg_type"], 0) + 1
    t0, t1 = new_rows[0]["msg_time"], new_rows[-1]["msg_time"]

    lines = []
    lines.append("解析报告 / parse report")
    lines.append("=" * 46)
    lines.append(f"源文件        : {target}")
    lines.append(f"批次号        : {batch_id}")
    lines.append(f"来源类型      : {args.source}")
    lines.append(f"会话名        : {args.chat_name or '(未指定)'}")
    lines.append(f"场景模式      : {args.mode}")
    lines.append(f"解析条数      : {len(new_rows)}")
    lines.append(f"时间范围      : {t0}  →  {t1}")
    lines.append(f"新增入库      : {len(added)}")
    lines.append(f"重复跳过      : {skipped}")
    lines.append(f"累计记录数    : {len(all_rows)}")
    lines.append("")
    lines.append("说话人分布：")
    for k, v in sorted(senders.items(), key=lambda x: -x[1]):
        lines.append(f"  {k:<16} {v:>3} 条")
    lines.append("")
    lines.append("消息类型分布：")
    for k, v in sorted(types.items(), key=lambda x: -x[1]):
        lines.append(f"  {k:<16} {v:>3} 条")
    report = "\n".join(lines)

    print(report)

    if args.stats:
        return

    with open(jsonl_path, "w", encoding="utf-8") as f:
        for r in all_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in all_rows:
            w.writerow(r)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report + "\n")

    print(f"\n[ok] 写入 {jsonl_path}")
    print(f"[ok] 写入 {csv_path}")
    print(f"[ok] 写入 {report_path}")


if __name__ == "__main__":
    main()
