# 文档地图 / Document map

每份核心文档都有中英两版，章节一一对应。这不是礼貌，是约束——由 [`tests/test_docs_bilingual.py`](../tests/test_docs_bilingual.py) 守着：章节数不一致、链接指向不存在的中英对照，测试就红。

Every core document exists in both Chinese and English, section for section. Not a courtesy — a constraint, enforced by [`tests/test_docs_bilingual.py`](../tests/test_docs_bilingual.py).

---

## 先读哪一份 / What to read first

| 你想知道 | 中文 | English |
|---|---|---|
| 这东西到底怎么用、凭什么可信 | [`../README.md`](../README.md) | [`../README_EN.md`](../README_EN.md) |
| 你们按什么标准交付（验收清单） | [`PRINCIPLES.md`](./PRINCIPLES.md) | [`PRINCIPLES_EN.md`](./PRINCIPLES_EN.md) |
| 和 Blender / C4D 到底差在哪，26 周怎么走 | [`ROADMAP.md`](./ROADMAP.md) | [`ROADMAP_EN.md`](./ROADMAP_EN.md) |
| 护城河、算法排序、商业顺序 | [`STRATEGY-2026.md`](./STRATEGY-2026.md) | [`STRATEGY-2026_EN.md`](./STRATEGY-2026_EN.md) |

---

## 工程文档 / Engineering notes

这些偏实现，只有中文版；它们的读者是改代码的人。

These are implementation notes, Chinese only — their audience is whoever touches the code.

| 文档 | 内容 |
|---|---|
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | 运行时分层、五个基元、装配求解、爆炸与剖切 |
| [`VALIDATION.md`](./VALIDATION.md) | 验证方法：无头渲染、像素统计、已踩过的坑 |
| [`DESIGN-NOTES.md`](./DESIGN-NOTES.md) | 视觉决策记录：为什么是暗房、为什么是胶片调色 |

---

## 阅读顺序建议 / Suggested order

**如果你要评估这个项目**：`README` → `PRINCIPLES`（看它敢不敢被否证）→ `ROADMAP`（看判据是不是真的可测）。

**如果你要接手代码**：`ARCHITECTURE` → `spec/schema/specsheet.schema.json` → `tools/spec_compile.py` → `tests/`。

**如果你要判断能不能合作**：`STRATEGY-2026`（它明确写了不做什么）→ `ROADMAP` P3（接口那一段）。

---

## 双语的规矩 / The bilingual rule

1. **不是翻译，是重写。** 英文版按英文读者的阅读习惯写，不逐字搬运中文句式。
2. **结构必须对齐。** 同一份文档的两版，一级标题数量和顺序必须一致。
3. **允许增补，不允许缺失。** 英文版可以多一句解释，但不能少一个结论。
4. **命令必须一致。** 同一段代码在两版里逐字相同——它们会被复制粘贴。

改文档时，两版一起改。测试不检查语义，但检查结构；语义那次，靠人。
