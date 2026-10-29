#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_db_payload.py —— records.jsonl → 资料库「数据表」建表 schema + 批量写入 payload

产出（默认写到 <out-dir>/db/）：
  schema.json            建表用，喂给 database/create_database.py --schema
  records_batch_01.json  写入用，每批 ≤100 条，喂给 batch_add_database_records.py --records
  mapping_report.txt     字段映射与告警

用法：
  python3 build_db_payload.py records.jsonl --out-dir kb
  python3 build_db_payload.py records.jsonl --out-dir kb --auto-topic   # 开启关键词自动归类

配套命令（$SKILL = library 技能目录）：
  python3 "$SKILL/database/create_database.py" --schema "$(cat kb/db/schema.json)"
  python3 "$SKILL/database/batch_add_database_records.py" --database-id "<id>" \\
      --records "$(cat kb/db/records_batch_01.json)"
"""

import argparse
import json
import os
import sys

# ---------------------------------------------------------------- 枚举定义

MSG_TYPES = ["文本", "图片", "语音", "视频", "文件", "链接", "表情",
             "小程序", "公众号", "混合", "红包", "转账", "位置", "名片", "接龙", "其他"]
TYPE_MAP = {
    "text": "文本", "image": "图片", "voice": "语音", "video": "视频",
    "file": "文件", "link": "链接", "sticker": "表情", "miniapp": "小程序",
    "official": "公众号", "mixed": "混合", "redpacket": "红包",
    "transfer": "转账", "location": "位置", "contact": "名片", "chain": "接龙",
}

TOPICS = ["学习", "工作", "情感", "生活", "观点", "素材",
          "家庭", "健康", "金钱", "社交", "技术", "娱乐", "未归类"]

TOPIC_KEYWORDS = {
    "学习": ["老师", "作业", "考试", "论文", "课程", "上课", "复习", "作业", "答辩", "导师", "研究"],
    "工作": ["项目", "会议", "汇报", "deadline", "排期", "老板", "客户", "方案", "需求", "交付"],
    "情感": ["喜欢", "难过", "想念", "分手", "眼泪", "犹豫", "开心", "爱你", "心动", "残忍"],
    "生活": ["吃饭", "睡", "天气", "周末", "出门", "房租", "地铁", "回家", "旅行"],
    "观点": ["我觉得", "我认为", "其实", "本质上", "所以说", "应该", "不该"],
    "素材": ["转发", "分享", "收藏", "链接", "文章", "公众号", "干货"],
    "家庭": ["爸", "妈", "爷爷", "奶奶", "姥姥", "姥爷", "家里", "亲戚", "孩子"],
    "健康": ["医院", "身体", "生病", "体检", "药", "失眠", "锻炼", "跑步"],
    "金钱": ["钱", "工资", "付", "转账", "买", "价格", "报销", "预算"],
    "社交": ["聚会", "约", "一起", "生日", "请客", "朋友", "群"],
    "技术": ["代码", "three.js", "python", "接口", "bug", "调试", "模型", "算法"],
    "娱乐": ["电影", "游戏", "音乐", "综艺", "追剧", "唱歌", "球赛"],
}

EMOTIONS = ["平静", "愉悦", "温暖", "感动", "思考", "焦虑",
            "难过", "愤怒", "疲惫", "兴奋", "无奈", "未知"]
EMOTION_KEYWORDS = {
    "愉悦": ["哈哈", "开心", "太好了", "好耶", "笑死"],
    "温暖": ["谢谢", "辛苦", "照顾", "陪", "想你"],
    "感动": ["眼泪", "哭", "感动"],
    "思考": ["为什么", "本质", "我觉得", "如果", "可能"],
    "焦虑": ["来不及", "怎么办", "担心", "紧张", "ddl"],
    "难过": ["难受", "失落", "遗憾", "残忍", "犹豫"],
    "愤怒": ["气死", "过分", "凭什么", "烦"],
    "疲惫": ["累", "困", "熬夜", "撑不住"],
    "兴奋": ["冲", "期待", "终于", "激动"],
    "无奈": ["算了", "没办法", "随便", "只能"],
}

MODES = [
    ("M01 冷存档", "M01"), ("M02 思想资源", "M02"), ("M03 生活日记", "M03"),
    ("M04 人物观察", "M04"), ("M05 金句库", "M05"), ("M06 关系档案", "M06"),
    ("M07 行动提取", "M07"), ("M08 情绪轨迹", "M08"), ("M09 知识卡片", "M09"),
    ("M10 选题池", "M10"), ("M11 家族记忆", "M11"), ("M12 决策复盘", "M12"),
]

# ---------------------------------------------------------------- 建表 schema

def build_schema(title, space_id=None, parent_id=None):
    props = [
        {"name": "记录ID", "config": {"text": ""}},
        {"name": "批次号", "config": {"text": ""}},
        {"name": "会话名", "config": {"text": ""}},
        {"name": "说话人", "config": {"text": ""}},
        {"name": "是否本人", "config": {"select": {"options": [
            {"text": "是"}, {"text": "否"}, {"text": "未知"}]}}},
        {"name": "消息时间", "config": {"date": {"format": "yyyy-mm-dd"}}},
        {"name": "小时", "config": {"number": {"decimalPlaces": 0, "useSeparate": False}}},
        {"name": "星期", "config": {"select": {"options": [
            {"text": w} for w in ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]]}}},
        {"name": "消息类型", "config": {"select": {"options": [
            {"text": t} for t in MSG_TYPES]}}},
        {"name": "内容", "config": {"text": ""}},
        {"name": "主题分类", "config": {"select": {"options": [
            {"text": t} for t in TOPICS]}}},
        {"name": "主题标签", "config": {"text": ""}},
        {"name": "情绪", "config": {"select": {"options": [
            {"text": e} for e in EMOTIONS]}}},
        {"name": "行动项", "config": {"text": ""}},
        {"name": "重要度", "config": {"number": {"decimalPlaces": 0, "useSeparate": False}}},
        {"name": "场景模式", "config": {"select": {"options": [
            {"text": m} for m, _ in MODES]}}},
        {"name": "隐私等级", "config": {"select": {"options": [
            {"text": "普通"}, {"text": "敏感"}, {"text": "机密"}]}}},
        {"name": "置信度", "config": {"select": {"options": [
            {"text": "高"}, {"text": "低"}]}}},
        {"name": "归档链接", "config": {"url": {"text": "", "link": ""}}},
        {"name": "指纹", "config": {"text": ""}},
    ]
    schema = {"title": title, "properties": props}
    if space_id:
        schema["space_id"] = space_id
    if parent_id:
        schema["parent_id"] = parent_id
    return schema


# ---------------------------------------------------------------- 值构造

def guess_topic(text):
    scores = {}
    for topic, kws in TOPIC_KEYWORDS.items():
        s = sum(1 for k in kws if k in text)
        if s:
            scores[topic] = s
    if not scores:
        return "未归类"
    return max(scores.items(), key=lambda x: x[1])[0]


def guess_emotion(text):
    for emo, kws in EMOTION_KEYWORDS.items():
        if any(k in text for k in kws):
            return emo
    return "未知"


def mode_label(code):
    for label, c in MODES:
        if c == code:
            return label
    return MODES[0][0]


def to_record(r, auto_topic=False):
    content = r.get("content_raw", "") or ""
    topic = r.get("topic_tags", "") or ""
    if auto_topic and not topic:
        topic = guess_topic(content)
    topic = topic if topic in TOPICS else "未归类"
    emo = r.get("emotion", "") or ""
    if auto_topic and not emo:
        emo = guess_emotion(content)
    emo = emo if emo in EMOTIONS else "未知"

    props = {
        "记录ID": {"text": r.get("record_id", "")},
        "批次号": {"text": r.get("batch_id", "")},
        "会话名": {"text": r.get("chat_name", "")},
        "说话人": {"text": r.get("sender", "unknown")},
        "是否本人": {"select": "未知"},
        "消息时间": {"date": (r.get("msg_time", "") or "").replace(" ", "T")[:19]},
        "小时": {"number": int(r.get("msg_hour", 0) or 0)},
        "星期": {"select": r.get("weekday", "周一")},
        "消息类型": {"select": TYPE_MAP.get(r.get("msg_type", "text"), "其他")},
        "内容": {"text": content[:1900]},
        "主题分类": {"select": topic},
        "主题标签": {"text": r.get("topic_tags", "")},
        "情绪": {"select": emo},
        "行动项": {"text": r.get("action_item", "")},
        "重要度": {"number": 0},
        "场景模式": {"select": mode_label(r.get("mode", "M01"))},
        "隐私等级": {"select": {"normal": "普通", "sensitive": "敏感",
                                "restricted": "机密"}.get(r.get("privacy_level", "normal"), "普通")},
        "置信度": {"select": "高" if r.get("confidence", "high") == "high" else "低"},
        "指纹": {"text": r.get("hash_dup", "")},
    }
    url = r.get("kb_url", "")
    if url:
        props["归档链接"] = {"url": {"text": "查看原文", "link": url}}
    return props


def main():
    ap = argparse.ArgumentParser(description="records.jsonl → 建表 schema + 批量写入 payload")
    ap.add_argument("jsonl")
    ap.add_argument("--out-dir", default="kb")
    ap.add_argument("--title", default="微信记忆库·记录表")
    ap.add_argument("--space-id", default="")
    ap.add_argument("--parent-id", default="")
    ap.add_argument("--auto-topic", action="store_true", help="用关键词猜测主题分类与情绪")
    ap.add_argument("--batch-size", type=int, default=100)
    ap.add_argument("--dry-run", action="store_true", help="只校验不写文件")
    args = ap.parse_args()

    if not os.path.exists(args.jsonl):
        sys.exit(f"[x] 文件不存在：{args.jsonl}")

    rows = []
    with open(args.jsonl, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    if not rows:
        sys.exit("[x] records.jsonl 为空")

    schema = build_schema(args.title, args.space_id or None, args.parent_id or None)
    payloads = [to_record(r, args.auto_topic) for r in rows]

    # ---- 自检：select 值必须在 options 内
    opt_index = {}
    for p in schema["properties"]:
        cfg = p["config"]
        if "select" in cfg:
            opt_index[p["name"]] = {o["text"] for o in cfg["select"]["options"]}
    errors = []
    for i, rec in enumerate(payloads):
        for k, v in rec.items():
            if k in opt_index and "select" in v and v["select"] not in opt_index[k]:
                errors.append(f"第{i+1}条 {k}={v['select']!r} 不在选项内")
            if k not in {p["name"] for p in schema["properties"]}:
                errors.append(f"第{i+1}条 字段 {k!r} 未在 schema 中定义")

    batches = [payloads[i:i + args.batch_size] for i in range(0, len(payloads), args.batch_size)]

    report = [
        "数据库 payload 报告",
        "=" * 46,
        f"源文件      : {args.jsonl}",
        f"记录条数    : {len(rows)}",
        f"字段数      : {len(schema['properties'])}",
        f"分批数      : {len(batches)}（每批 ≤{args.batch_size}）",
        f"自动归类    : {'开' if args.auto_topic else '关'}",
        f"schema 校验 : {'通过' if not errors else f'{len(errors)} 处问题'}",
    ]
    if errors:
        report.append("")
        report.append("问题明细：")
        report.extend("  - " + e for e in errors[:30])

    text = "\n".join(report)
    print(text)

    if args.dry_run:
        return
    if errors:
        sys.exit("[x] 存在选项/字段不匹配，已中止写入（避免服务端 11607 报错）")

    dbdir = os.path.join(args.out_dir, "db")
    os.makedirs(dbdir, exist_ok=True)
    with open(os.path.join(dbdir, "schema.json"), "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)
    for i, b in enumerate(batches, 1):
        with open(os.path.join(dbdir, f"records_batch_{i:02d}.json"), "w", encoding="utf-8") as f:
            json.dump(b, f, ensure_ascii=False, indent=2)
    with open(os.path.join(dbdir, "mapping_report.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")

    print(f"\n[ok] {dbdir}/schema.json")
    print(f"[ok] {dbdir}/records_batch_*.json（{len(batches)} 个）")
    print("\n下一步：")
    print(f'  python3 "$SKILL/database/create_database.py" --schema "$(cat {dbdir}/schema.json)"')
    print(f'  python3 "$SKILL/database/batch_add_database_records.py" \\')
    print(f'      --database-id "<返回的 database_id>" \\')
    print(f'      --records "$(cat {dbdir}/records_batch_01.json)"')


if __name__ == "__main__":
    main()
