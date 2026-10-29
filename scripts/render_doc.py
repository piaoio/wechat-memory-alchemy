#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_doc.py —— records.jsonl → 标准存档 Markdown（可直接喂给资料库 create_doc.py）

正文固定四段：抬头 → 原始内容 → 结构化摘要 → 说明

用法：
  python3 render_doc.py records.jsonl [--out 存档.md] [--group day|batch|sender|none]
                          [--title PREFIX] [--split] [--out-dir DIR] [--batch-id ID]

  --group day   按日期分段（默认）
  --group batch 按批次分段
  --group sender 按说话人分段
  --group none  不分段
  --split       每段单独生成一个 .md 文件（便于批量建文档）
"""

import argparse
import json
import os
import re
import sys
from collections import OrderedDict


def load(path):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    rows.sort(key=lambda r: (r.get("msg_time", ""), r.get("record_id", "")))
    return rows


def safe_name(s):
    return re.sub(r'[\\/:*?"<>|\s]+', "_", s).strip("_") or "untitled"


def quote_block(text, prefix=""):
    """把多行文本渲染成 Markdown 引用块。"""
    out = []
    for ln in text.split("\n"):
        if ln.strip():
            out.append(prefix + ln.rstrip())
        else:
            out.append(prefix.rstrip())
    return "\n".join(out)


def render_section(rows, heading=None):
    """生成一个分段（一个 group）的 Markdown 正文。"""
    md = []
    h = "###" if heading else "##"
    if heading:
        md.append(f"## {heading}")
        md.append("")

    senders = OrderedDict()
    for r in rows:
        senders[r.get("sender", "unknown")] = senders.get(r.get("sender", "unknown"), 0) + 1
    name_list = "、".join(senders.keys())
    t0 = rows[0].get("msg_time", "")
    t1 = rows[-1].get("msg_time", "")
    batch = rows[0].get("batch_id", "")
    src = rows[0].get("source_type", "chat")

    src_cn = {"chat": "微信聊天记录分享", "favorite": "微信收藏整理",
              "moments": "朋友圈整理", "official": "公众号文章整理",
              "mixed": "微信混合来源"}.get(src, src)

    # ---- 抬头
    md.append(f"> 来源：{src_cn}　｜　发送人：{name_list}　｜　共 {len(rows)} 条消息")
    md.append(f"> 时间范围：{t0} 至 {t1}　｜　批次号：{batch or '未标注'}")
    md.append("")

    # ---- 原始内容
    md.append(f"{h} 原始内容")
    md.append("")
    for r in rows:
        t = r.get("msg_time", "")
        hm = t[11:16] if len(t) >= 16 else t
        sender = r.get("sender", "unknown")
        md.append(f"> **{sender}** · {hm}")
        md.append(">")
        body = r.get("content_raw", "") or "（空）"
        if r.get("media_desc"):
            body = body + f"\n〔媒介：{r['media_desc']}〕"
        md.append(quote_block(body, "> "))
        md.append("")

    # ---- 结构化摘要
    md.append(f"{h} 结构化摘要")
    md.append("")
    md.append(f"- 消息类型：{'、'.join(sorted({r.get('msg_type', '') for r in rows}))}")
    tags = sorted({r.get("topic_tags") for r in rows if r.get("topic_tags")})
    if tags:
        md.append(f"- 主题标签：{'、'.join(tags)}")
    emos = sorted({r.get("emotion") for r in rows if r.get("emotion")})
    if emos:
        md.append(f"- 情绪标记：{'、'.join(emos)}")
    acts = [r.get("action_item") for r in rows if r.get("action_item")]
    if acts:
        md.append(f"- 行动项：{len(acts)} 项")
        for a in acts:
            md.append(f"  - {a}")
    md.append(f"- 说话人条数：{'；'.join(f'{k} {v} 条' for k, v in senders.items())}")
    if rows[0].get("mode"):
        md.append(f"- 归档模式：{rows[0]['mode']}")
    md.append("")

    # ---- 说明
    md.append(f"{h} 说明")
    md.append("")
    md.append(f"- 记录时间：{t0}" + ("" if t0 == t1 else f" 至 {t1}"))
    md.append(f"- 记录类型：" + ("单条消息（聊天记录分享）" if len(rows) == 1
                                 else f"聊天记录包，共 {len(rows)} 条"))
    md.append(f"- 数据来源：WorkBuddy 微信分享入口 · 批次 {batch or '未标注'}")
    md.append("- 备注：原文按分享顺序保存；结构化字段见 records.csv，本页仅保留可读正文。")
    md.append("")
    return "\n".join(md)


def main():
    ap = argparse.ArgumentParser(description="records.jsonl → 标准存档 Markdown")
    ap.add_argument("jsonl")
    ap.add_argument("--out", default="", help="输出 md 路径（--split 时作为目录下的文件名前缀）")
    ap.add_argument("--out-dir", default=".", help="--split 时的输出目录")
    ap.add_argument("--group", default="day", choices=["day", "batch", "sender", "none"])
    ap.add_argument("--title", default="微信聊天记录存档", help="文档标题前缀")
    ap.add_argument("--split", action="store_true", help="每个分段单独输出一个 md")
    args = ap.parse_args()

    if not os.path.exists(args.jsonl):
        sys.exit(f"[x] 文件不存在：{args.jsonl}")

    rows = load(args.jsonl)
    if not rows:
        sys.exit("[x] records.jsonl 为空")

    if args.group == "none":
        groups = OrderedDict([("全部", rows)])
    elif args.group == "day":
        groups = OrderedDict()
        for r in rows:
            groups.setdefault(r.get("msg_date", "未知日期"), []).append(r)
    elif args.group == "batch":
        groups = OrderedDict()
        for r in rows:
            groups.setdefault(r.get("batch_id", "未标注批次"), []).append(r)
    else:
        groups = OrderedDict()
        for r in rows:
            groups.setdefault(r.get("sender", "unknown"), []).append(r)

    if args.split:
        os.makedirs(args.out_dir, exist_ok=True)
        made = []
        for key, grp in groups.items():
            title = f"{args.title}（{key}）"
            md = [f"---", f'title: "{title}"', "---", "", render_section(grp)]
            fp = os.path.join(args.out_dir, f"{safe_name(title)}.md")
            with open(fp, "w", encoding="utf-8") as f:
                f.write("\n".join(md))
            made.append(fp)
        print(f"[ok] 生成 {len(made)} 个文件：")
        for p in made:
            print("     ", p)
        return

    md = []
    if len(groups) == 1:
        key = list(groups.keys())[0]
        title = f"{args.title}（{key}）" if args.group != "none" else args.title
        md += ["---", f'title: "{title}"', "---", ""]
        md.append(render_section(list(groups.values())[0]))
    else:
        md += ["---", f'title: "{args.title}"', "---", ""]
        for key, grp in groups.items():
            md.append(render_section(grp, heading=str(key)))
            md.append("---")
            md.append("")

    out = args.out or os.path.join(args.out_dir, f"{safe_name(args.title)}.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(md).rstrip() + "\n")
    print(f"[ok] 写入 {out}（{len(rows)} 条，{len(groups)} 个分段）")


if __name__ == "__main__":
    main()
