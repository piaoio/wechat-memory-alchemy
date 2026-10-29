# 资料库命令速查（均已在真实环境验证）

先加载 `library` 技能，再按下表操作。命令里的 `$SKILL` 指向 **WorkBuddy 内置的 `library` 技能目录**（不是你自己的 skill 目录）。

## `$SKILL` 怎么定位

**没有现成的环境变量可用**——`CODEBUDDY_SKILL_DIR` 这类变量在运行时并不存在，别照抄网上的写法。而且**也不能从 `%LOCALAPPDATA%` 推**：实测有机器把 WorkBuddy 装在 D 盘而 `%LOCALAPPDATA%` 指向 C 盘，照推会得到错误路径。

**① 最省事：让 WorkBuddy 自己找。** 在对话里直接说"用 library 技能的资料库脚本建文档"，它会定位到安装目录的绝对路径。人不需要记路径，也不需要猜盘符。

**② 必须手工执行时，从安装目录往下走：**

先拿到 WorkBuddy 安装目录（含 `WorkBuddy.exe` 那一层）：

- **Windows**：桌面或开始菜单图标 → 右键 → **打开文件所在位置**
- **macOS**：`/Applications/WorkBuddy.app` → 右键 → **显示包内容** → `Contents`

然后拼上固定后缀：

```
<安装目录>/resources/app.asar.unpacked/resources/plugins/workbuddy-builtin/skills/library
```

macOS 是 `<Contents>/Resources/app.asar.unpacked/...`（大小写不同）。判据：这个目录里应该有 `space_api.py`、`doc/`、`database/`、`manage/` 四个东西，缺一个就是路径错了。

```bash
SKILL="<上一步得到的绝对路径>"
ls "$SKILL/space_api.py" "$SKILL/doc" "$SKILL/database"   # 三个都在才算对
```

> 所有脚本的身份由运行时注入，**不要手工传 token**。

---

## 1. 找到目标空间与文件夹

```bash
# 列出我的空间，拿 space_id
python3 "$SKILL/space_api.py" space.workspace.list-user-spaces --limit 100

# 列根目录，拿 parent_node_id
python3 "$SKILL/space_api.py" space.workspace.list-nodes \
    --space-id "<space_id>" --limit 100

# 列某个文件夹下已有内容（避免重复建档）
python3 "$SKILL/space_api.py" space.workspace.list-nodes \
    --space-id "<space_id>" --parent-node-id "<folder_id>" --limit 100
```

**建档前必做**：列一次目标文件夹，确认没有同批次/同内容的文档。重复建档比漏档更难收拾。

---

## 2. 建文件夹

```bash
python3 "$SKILL/manage/create_folder.py" --title "微信记忆库" --space-id "<space_id>"
```

输出含 `node_id`，后续作为 `--parent-id`。

---

## 3. 建档（文档）

```bash
# ① 先用脚本渲染标准 Markdown
python3 scripts/render_doc.py kb/records.jsonl --group day --out /tmp/out.md

# ② 再建文档
python3 "$SKILL/doc/create_doc.py" \
    --title "微信聊天记录存档（2026-10-29 13:44）" \
    --space-id "<space_id>" \
    --parent-id "<folder_id>" \
    --content-file "/tmp/out.md"
```

要点：
- 正文走 `--content-file`（中文长文本用参数直传容易踩引号转义）
- 建完立刻 `get_doc_reviews.py` 回读校验，确认段落类型（引用块 / 有序列表）没走样
- 临时 md 用完删掉，别留在项目目录

```bash
# 回读校验
python3 "$SKILL/doc/get_doc_reviews.py" --page-id "<page_id>"
```

---

## 4. 建「数据表」（结构化最强形态）

比文档强的地方：**字段有类型**，可按日期/情绪/主题筛选排序，可增量追加。

```bash
# ① 生成建表 schema
python3 scripts/build_db_payload.py kb/records.jsonl --out-dir kb --auto-topic

# ② 建表
python3 "$SKILL/database/create_database.py" --schema "$(cat kb/db/schema.json)"
# → 返回 {"database_id": "...", "space_id": "...", "properties": [...], "url": "..."}

# ③ 批量写记录（每批 ≤100 条）
python3 "$SKILL/database/batch_add_database_records.py" \
    --database-id "<database_id>" \
    --records "$(cat kb/db/records_batch_01.json)"

# ④ 查表结构 / 查数据
python3 "$SKILL/database/get_database_schema.py" --database-id "<database_id>"
python3 "$SKILL/database/get_database_content.py" --database-id "<database_id>"
```

### 三个必须记住的坑

1. **选项不匹配会报 `11607`**：`select` / `multi_select` 的值必须在字段选项里，服务端**不会自动新建选项**。先 `add_database_field` 补选项，再写值。
   `build_db_payload.py` 已内置本地校验，不匹配直接中止，不会打到服务端。
2. **`success: true` 不等于写入成功**：这个接口可能返回成功但实际没落库。交付前用 `get_database_record.py --record-id <rid>` 抽样复验。
3. **字段名必须完全一致**（中文也算），含空格差异会失败。

字段类型与写值格式的权威定义在 `library` 技能 `database/params-reference.md`（§PropertyConfig / §PropertyValue），遇到不确定的字段类型先查那里，不要猜。

---

## 5. 移动与整理

```bash
python3 "$SKILL/space_api.py" space.workspace.move-node \
    --node-id "<node_id>" \
    --target-parent-id "<folder_id>" \
    --target-space-id "<space_id>"
```

用于把根目录下散落的存档收进「微信记忆库」。

---

## 6. 编辑已有文档

```bash
python3 "$SKILL/doc/submit_doc_edit.py" --page-id "<page_id>" \
    --actions-json '[{"type":"...","...":"..."}]'
```

动作结构较复杂，先用 `--dry-run` 验证再提交。改完仍要回读校验。
注意：**改写会覆盖人工修改**，编辑前先回读一次确认当前内容。

---

## 7. 检索

```bash
# 按关键词搜整个空间
python3 "$SKILL/space_api.py" space.searcher.search-nodes \
    --space-id "<space_id>" --query "犹豫" --limit 20
```

跨库检索用 `knowledge_search` 工具（会同时覆盖资料库、腾讯文档、知识库）。

---

## 8. 常见报错对照

| 现象 | 原因 | 处理 |
|---|---|---|
| `11607` | select 选项不存在 | 先补选项再写 |
| 建表成功但字段是文本 | `config` 里 oneof 写错（如同时给了两个类型键） | 一个字段只能有一个类型键 |
| 文档正文全挤成一段 | Markdown 空行缺失 | 段落之间必须有空行 |
| 有序列表变成纯文本 | 列表项前缺 `> ` 且无空行分隔 | 引用块内每行都要带 `>` |
| 中文乱码 | 文件编码非 UTF-8 | 写 md 时显式 `encoding="utf-8"` |
| 建了空文档 | `--content-file` 路径错但文件存在为空 | 建完立刻回读校验 |

---

## 9. 一次完整归档的标准动作序列

```bash
# 0) 读原文
cat "<extracted_dir_path>/聊天记录.txt"

# 1) 解析 + 去重合并
python3 scripts/build_records.py "<extracted_dir_path>" \
    --out-dir kb --source chat --batch-id "20261029_1344" --chat-name "私聊"

# 2) 渲染文档
python3 scripts/render_doc.py kb/records.jsonl --group batch --out /tmp/out.md

# 3) 确认目标文件夹无重复
python3 "$SKILL/space_api.py" space.workspace.list-nodes \
    --space-id "<space_id>" --parent-node-id "<folder_id>" --limit 100

# 4) 建档
python3 "$SKILL/doc/create_doc.py" --title "微信聊天记录存档（2026-10-29 13:44）" \
    --space-id "<space_id>" --parent-id "<folder_id>" --content-file /tmp/out.md

# 5) 回读校验 + 清理临时文件
python3 "$SKILL/doc/get_doc_reviews.py" --page-id "<page_id>"
rm -f /tmp/out.md
```
