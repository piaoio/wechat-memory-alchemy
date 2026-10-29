# 微信记忆炼金术 · WeChat Memory Alchemy

> 微信里存着你十年的生活，但它只肯一条一条地给你。

一个 WorkBuddy Skill：把微信里的**聊天记录、收藏、朋友圈、公众号文章**搬进个人知识库，压成带人名、时间、主题、情绪、行动项的结构化记录，再按 12 种场景模式重新组装成你能用的东西。

---

## 它解决的问题

微信不开放数据接口，所有内容只能由用户在客户端里主动"分享"。这就带来三个真问题：

1. **怎么搬** —— 一次只有一个分享单元，怎么把它高效搬进 WorkBuddy 资料库？
2. **怎么炼** —— 一堆口语流水，怎么变成能筛选、能统计、能追溯的结构化记录？
3. **怎么用** —— 同一批数据，怎么变成"我的思想库""我的日记""某人的观察笔记"？

这个 Skill 把三件事都写成了可执行流程，附三个纯标准库 Python 脚本。

---

## 核心设计

### 单元素原则

一次分享 = 一个分享单元 = 一次处理。

批量必须由用户在微信端完成：**多选消息（按需顺序）→ 合并转发 → 分享到 WorkBuddy**。
顺序即语义，乱序等于语义污染。这不是技术限制，是数据来源的现实。

### 三层结构

```
原始层  raw/        原封不动的包与原文     ← 永不可再生，绝不修改
规范层  records     一行一条消息，28 字段   ← 可筛选、可去重、可增量合并
派生层  topics/people/timeline            ← 可随时重算
```

铁律：**第 3 层可以重算，第 1 层不能重建。** 所以原文永远保留，摘要只是叠加。

### 12 种场景模式

| 编号 | 模式 | 一句话 |
|---|---|---|
| M01 | 冷存档 | 原样封存，可检索（默认） |
| M02 | 思想资源 | 把口语里的主张剥离成命题卡 |
| M03 | 生活日记 | 朋友圈 → 日记体时间轴 |
| M04 | 人物观察 | 关注的人 → 议题偏好与观点演变 |
| M05 | 金句库 | 可独立引用的表达 |
| M06 | 关系档案 | 与某人的往来史、承诺与兑现 |
| M07 | 行动提取 | 约定 → 待办 |
| M08 | 情绪轨迹 | 情绪 → 时间序列 |
| M09 | 知识卡片 | 干货 → 概念卡 |
| M10 | 选题池 | 素材 → 选题假设 |
| M11 | 家族记忆 | 长辈语音 → 口述史 |
| M12 | 决策复盘 | 重要对话 → 决策记录 |

---

## 安装

把整个目录放到 WorkBuddy 的用户技能目录：

```bash
git clone https://github.com/<you>/wechat-memory-alchemy.git \
  ~/.workbuddy/skills/wechat-memory-alchemy
```

重启 WorkBuddy，说"存到知识库"或"把朋友圈做成日记"即可触发。

---

## 目录结构

```
wechat-memory-alchemy/
├── SKILL.md                      # 主入口：何时用、5 步工作流、硬边界
├── references/
│   ├── ingest.md                 # 四条采集入口的实际操作
│   ├── schema.md                 # 28 字段定义、三层结构、目录约定
│   ├── modes.md                  # 12 个场景模式卡 + 配置模板
│   ├── media-handling.md         # 文本/图片/语音/视频/文件/链接/表情 处理矩阵
│   ├── boundaries.md             # 能力边界、合规红线、脱敏、越界话术
│   └── library-cli.md            # 资料库命令速查（含数据表 API 的三个坑）
└── scripts/
    ├── build_records.py          # 聊天记录包 → records.jsonl/csv（去重合并）
    ├── render_doc.py             # records → 标准存档 Markdown
    └── build_db_payload.py       # records → 资料库数据表 schema + 批量写入
```

---

## 脚本用法

三个脚本纯标准库，无第三方依赖。

```bash
# 1) 聊天记录包 → 结构化记录表（自动与既有结果去重合并）
python3 scripts/build_records.py "<聊天记录.txt 或其目录>" \
    --out-dir kb --source chat --batch-id 20261029_1344 --chat-name "私聊"

# 2) 记录表 → 标准存档 Markdown（可直接喂给资料库建档）
python3 scripts/render_doc.py kb/records.jsonl --group day --out out.md

# 3) 记录表 → 资料库数据表 schema + 批量写入 payload
python3 scripts/build_db_payload.py kb/records.jsonl --out-dir kb --auto-topic
```

`build_records.py` 兼容多种时间格式（`2026年10月29日 12:52`、`2026-10-29 12:52`、`下午3:20`），
把多行消息合并为一条，按 `发送人+时间+内容` 生成去重指纹。

---

## 边界

- 没有"批量导入"这个动作，也没有"全量同步"
- 不破解本地数据库，不逆向客户端，不抓取他人朋友圈
- 他人的发言属第三方信息，默认敏感，不外传
- 基于聊天记录只做**言论特征描述**，不做人格诊断

完整规则与越界请求的回应话术见 `references/boundaries.md`。

---

## License

MIT
