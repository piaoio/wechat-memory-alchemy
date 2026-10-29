---
name: wechat-memory-alchemy
display_name: "微信记忆炼金术"
display_name_en: "WeChat Memory Alchemy"
description: "把微信里的聊天记录、收藏、朋友圈、公众号文章搬进 WorkBuddy 资料库，压成带人名、时间、主题、情绪、行动项的结构化记录，并按 12 种场景模式（思想资源、生活日记、人物观察、金句库、关系档案、家族记忆等）重新组装成个人知识库。覆盖文本/图片/语音/文件/链接各媒介的处理路径，以及单元素与合并转发的批量边界规则。"
description_zh: "把微信里的聊天记录、收藏、朋友圈、公众号文章搬进 WorkBuddy 资料库，压成带人名、时间、主题、情绪、行动项的结构化记录，并按 12 种场景模式（思想资源、生活日记、人物观察、金句库、关系档案、家族记忆等）重新组装成个人知识库。覆盖文本/图片/语音/文件/链接各媒介的处理路径，以及单元素与合并转发的批量边界规则。触发词：存到知识库、整理聊天记录、微信收藏怎么整理、把朋友圈变成日记、整理关注的人的内容、建个人知识库、微信记录归档。"
description_en: "Turn WeChat chats, Favorites, Moments and Official Account articles into a structured personal knowledge base inside WorkBuddy Library. Normalizes messages into dated records with speaker, topic, emotion and action-item fields, then reassembles them through 12 configurable scenario modes (thought vault, life log, people watch, quote bank, family archive, etc.). Also defines the single-unit ingest boundary and the merge-forward batching rule."
version: "1.0.0"
author: "piaoio"
agent_created: true
---

# 微信记忆炼金术 —— 把聊天记录、收藏、朋友圈炼成你的第二大脑

微信里存着你十年的生活，但它只肯一条一条地给你。

这套 skill 解决三件事：

1. **怎么搬** —— 把聊天记录、收藏、朋友圈、公众号文章，一次一个"分享单元"搬进 WorkBuddy 资料库；
2. **怎么炼** —— 把口语化流水压成带 `说话人 / 时间 / 类型 / 主题 / 情绪 / 行动项` 的规范记录表；
3. **怎么用** —— 按选定"模式"重新组装：思想库、生活日记、人物观察、金句本、家族口述史……

---

## 何时启用

- 用户分享 `@wechat-chat-history:"聊天记录_*.zip"`，并说"存到知识库 / 归档 / 整理一下"
- 用户说"把微信收藏 / 朋友圈 / 公众号文章整理进知识库"
- 用户要建某种"模式"的个人库（思想资源、生活日记、人物观察、金句库……）
- 用户问"微信里的东西能不能一次性全导进来" → 直接读 `references/boundaries.md`，先讲清边界再动手
- 用户已有一堆存档文档，要"统一格式 / 补索引 / 重新归类"

不要用于：实时监听微信、破解本地数据库、批量抓取他人朋友圈（见边界章）。

---

## 第一原则：单元素

**一次分享 = 一个分享单元 = 一次处理。**

WorkBuddy 拿不到微信数据库，只有三种东西会到达：

| 到达形态 | 内容 | 处理方式 |
|---|---|---|
| 聊天记录包 | 一个 `.zip`，内含 `聊天记录.txt` | 解析 → 结构化 → 归档 |
| 文件 | 图片 / PDF / docx / 录音 | 按媒介路由（`references/media-handling.md`） |
| 链接 | 公众号文章 / 网页卡片 | 抓正文，失败则降级存"标题 + 链接 + 用户口述" |

**批量必须由用户在微信端完成**：多选消息（按所需顺序）→「合并转发」→ 分享到 WorkBuddy。顺序即语义，乱序等于语义污染。完整规则见 `references/boundaries.md`。

---

## 标准工作流（5 步）

### Step 0 接收与验真

用户分享后，上下文会带 `extracted_dir_path`。先确认事实，不要凭印象：

```bash
cat "<extracted_dir_path>/聊天记录.txt"
```

核对四件事：**发送人 / 时间 / 条数 / 是否与库中已有记录重复**。
若已有同名或同内容文档，先报告重复、不重复建（用户明确要求另存才建）。

### Step 1 落盘与解析

```bash
python3 scripts/build_records.py "<extracted_dir_path>" \
    --out-dir "<项目目录>/kb" --source chat --batch-id "20261029_1344"
```

产出 `records.jsonl`（一行一条）、`records.csv`（Excel 可开）、`parse_report.txt`（条数 / 时间范围 / 说话人 / 类型分布 / 去重结果）。
与既有 `records.jsonl` 自动合并去重（按 `hash_dup`），不会重复计数。

### Step 2 选模式

问一句或直接推断，把本条数据归入一个场景模式。模式决定"抽什么、丢什么、产出什么"：

- 用户没提需求 → 默认 **M01 冷存档**（原样封存，永不丢信息）
- 用户说"这是我的想法 / 灵感 / 观点" → **M02 思想资源**
- 用户说"朋友圈 / 日记 / 记录生活" → **M03 生活日记**
- 用户说"关注的人 / 博主 / 有意思的内容 / 分析一下" → **M04 人物观察**

十二种模式的完整卡片见 `references/modes.md`。**模式一旦确定，写进 `微信记忆库/_模式配置.md`**，后续同一批数据沿用，不要每次重新问。

### Step 3 结构化与去重

字段定义见 `references/schema.md`（28 字段 / 三层结构）。
必填最小集：`msg_time`、`sender`、`msg_type`、`content_raw`、`topic_tags`、`mode`。
其余能推就推，推不出就留空——**空字段比错字段安全**。

### Step 4 归档资料库

用 `library` skill 的脚本写入。目录约定、命令速查见 `references/library-cli.md`：

```bash
# 1) 确认空间与目标文件夹（先查重，避免重复建档）
python3 "$SKILL/space_api.py" space.workspace.list-user-spaces --limit 100
python3 "$SKILL/space_api.py" space.workspace.list-nodes --space-id "<space>" --parent-node-id "<folder>" --limit 100

# 2) 由 records 渲染标准存档 Markdown
python3 scripts/render_doc.py records.jsonl --group day --out out.md

# 3) 建文档
python3 "$SKILL/doc/create_doc.py" --title "微信聊天记录存档（2026-10-29 13:44）" \
    --space-id "<space>" --parent-id "<folder>" --content-file out.md
```

文档正文模板固定为四段：**抬头（来源/发送人/条数）→ 原始内容 → 结构化摘要 → 说明**。
结构化明细不要塞进文档，放 `records.csv`，文档只留人读得懂的部分。

**需要按字段筛选/统计时，改用「数据表」而非文档**（字段有类型，可按日期、情绪、主题筛选）：

```bash
python3 scripts/build_db_payload.py records.jsonl --out-dir kb --auto-topic
python3 "$SKILL/database/create_database.py" --schema "$(cat kb/db/schema.json)"
python3 "$SKILL/database/batch_add_database_records.py" \
    --database-id "<id>" --records "$(cat kb/db/records_batch_01.json)"
```

数据表落库的三个坑（选项 11607、假成功、字段名严格匹配）见 `references/library-cli.md` §4。

### Step 5 汇报与索引

每次归档后更新 `微信记忆库/INDEX.md`（条目数、时间跨度、模式分布、最近 5 条）。
向用户汇报时必须给出：**存到哪（路径 + 链接）、存了几条、用了什么模式、下一步能做什么**。

---

## 脚本

| 脚本 | 作用 | 关键参数 |
|---|---|---|
| `scripts/build_records.py` | 聊天记录包 → `records.jsonl/csv`，自动去重 | `--out-dir` `--source` `--chat-name` `--batch-id` `--stats` |
| `scripts/render_doc.py` | records → 标准存档 Markdown | `--group day\|batch\|sender\|none` `--split` `--title` |
| `scripts/build_db_payload.py` | records → 资料库数据表 schema + 批量写入 payload（含选项自检） | `--out-dir` `--auto-topic` `--dry-run` |

三个脚本纯标准库，无第三方依赖，Windows / macOS 通用。

---

## 模式路由（摘要）

| 编号 | 模式 | 一句话 | 典型触发 |
|---|---|---|---|
| M01 | 冷存档 | 原样封存，可检索 | "先存着" |
| M02 | 思想资源 | 只留你的判断与灵感 | "这是我的想法" |
| M03 | 生活日记 | 朋友圈 → 日记体 | "记录生活" |
| M04 | 人物观察 | 关注的人 → 画像 | "分析这个人" |
| M05 | 金句库 | 可引用的表达 | "攒素材 / 文案" |
| M06 | 关系档案 | 与某人的往来史 | "和 X 的聊天" |
| M07 | 行动提取 | 约定 → 待办 | "有什么要做的" |
| M08 | 情绪轨迹 | 情绪 → 时间序列 | "我最近状态" |
| M09 | 知识卡片 | 干货 → 卡片 | "群里分享的资料" |
| M10 | 选题池 | 内容 → 选题假设 | "做自媒体" |
| M11 | 家族记忆 | 长辈语音 → 口述史 | "家里的老照片" |
| M12 | 决策复盘 | 重要对话 → 决策记录 | "当时为什么这么定" |

详见 `references/modes.md`。

---

## 媒介路由（摘要）

| 媒介 | 主路径 | 兜底 |
|---|---|---|
| 纯文本 | 直接解析 | — |
| 图片 / 截图 | `ViewImage` 取文字与场景 | 存路径 + 一句话描述 |
| 语音 | 先转文字（微信"转文字"或 `AudioTranscribe`） | 记 `[语音 12"］` + 时长 |
| 文件 | office / pdf 技能抽取正文 | 存文件名 + 哈希 |
| 公众号 / 网页 | `WebFetch` 抓正文 | 标题 + 链接 + 用户口述 |
| 表情 / 贴纸 | 记 `[表情]` + 情绪标签 | — |
| 视频 | 封面 + 时长 + 标题 | 不入库原文件 |

详见 `references/media-handling.md`。

---

## 结构化产物（能炼出什么）

同一批原始数据，可以产出四种形态的东西，按需选：

| 形态 | 长什么样 | 用来干什么 | 生成方式 |
|---|---|---|---|
| **记录表** | 一行一条消息，28 字段（人/时间/类型/主题/情绪/行动项/隐私等级…） | 筛选、统计、横向比较 | `build_records.py` |
| **时间轴** | 按日/月排的叙事线 | 回溯"那段时间发生了什么" | `render_doc.py --group day` |
| **人物档案** | 一人一页：议题偏好、表达特征、观点演变 | 理解某个人 | M04 模式 |
| **主题聚合** | 按 13 类主题重排的卡片集 | 找素材、查资料 | M02/M09 模式 |

**工具分工**：解析用 Python（纯标准库）；沉淀用资料库（文档 / 数据表）；看图用 `ViewImage`；抓网页用 `WebFetch`；转语音用 `AudioTranscribe`；Office/PDF 抽取走 `workbuddy-office-routing`；检索用 `knowledge_search`；定期回顾用 automation。

完整字段定义与三层结构见 `references/schema.md`。

---

## 硬边界（不可逾越）

1. **不能全量同步**：没有"扫描我全部微信"这种操作，只能一个个分享单元进来。
2. **不能替他人生成**：只能处理用户自己分享出来的内容；他人的朋友圈、私聊无法抓取。
3. **不碰本地数据库**：不解析 `EnMicroMsg.db`、不逆向微信客户端——既不可靠也不合规。
4. **顺序不可乱**：合并转发必须按用户需要的顺序选；乱序数据要标注 `order_confidence: low`。
5. **单包上限**：建议 ≤ 500 条 / ≤ 20MB，超了按日期或话题切段，逐段批处理。
6. **敏感信息不落库**：身份证号、银行卡、密码、住址、健康诊断等先脱敏再入库（规则见 `references/boundaries.md`）。
7. **不虚构**：OCR 错字、语音转写错误必须标注 `confidence: low`，不得当成原话引用。

---

## 质量自检清单

归档前逐项过：

- [ ] 条数与时间范围已核对，无截断
- [ ] 已与库中既有记录去重，未重复建档
- [ ] 每条都有 `msg_time` + `sender`（缺失的标 `unknown` 而非留空猜测）
- [ ] 说话人姓名保持原样，未擅自改写昵称
- [ ] 图片/语音等非文本已给出一句话描述，不是空占位
- [ ] 隐私字段已脱敏
- [ ] 文档正文四段齐全，链接可打开
- [ ] `INDEX.md` 已更新

## 反模式（别做）

- ❌ 把所有内容一股脑贴上文档、不做结构化 → 库越大越不可用
- ❌ 为了"完整"把每条消息都单独建一个文档 → 目录爆炸
- ❌ 用户没要总结却自作主张写一堆感受 → 冷存档模式下保持沉默
- ❌ 用一句话概括掉整段对话却丢弃原文 → 原文必须留，摘要是叠加层
- ❌ 假设"这条肯定是 XX 说的" → 无 sender 就标 unknown
