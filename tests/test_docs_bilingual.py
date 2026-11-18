#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""双语契约测试。

守三件事：

1. **成对存在** —— 每份核心中文文档都必须有英文版，反之亦然
2. **结构对齐** —— 一级标题数量一致（不做语义判断，那是人的事）
3. **链接可达** —— 文档里指到的中英对照、图片、示例文件必须真的在

为什么用测试守而不是用规矩守：文档一旦允许单边更新，两边就会开始讲两个
不同的产品；而读者永远先读到错的那一版。

跑法：python3 -m pytest tests/test_docs_bilingual.py -q
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# (中文, 英文) —— 根目录的 README 与 docs/ 下的核心文档
PAIRS = [
    (ROOT / "README.md", ROOT / "README_EN.md"),
    (ROOT / "docs" / "PRINCIPLES.md", ROOT / "docs" / "PRINCIPLES_EN.md"),
    (ROOT / "docs" / "ROADMAP.md", ROOT / "docs" / "ROADMAP_EN.md"),
    (ROOT / "docs" / "STRATEGY-2026.md", ROOT / "docs" / "STRATEGY-2026_EN.md"),
]


def h2(path: Path) -> list[str]:
    return [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.startswith("## ")]


@pytest.mark.parametrize("zh,en", PAIRS, ids=[p[0].name for p in PAIRS])
def test_both_versions_exist(zh: Path, en: Path):
    assert zh.is_file(), f"缺中文版：{zh}"
    assert en.is_file(), f"缺英文版：{en}"


@pytest.mark.parametrize("zh,en", PAIRS, ids=[p[0].name for p in PAIRS])
def test_sections_align(zh: Path, en: Path):
    """一级标题数量必须一致。

    只查数量不查标题文字：英文版允许重写标题（它该按英文习惯写），
    但结构不能一边多出两节、一边少两节 —— 那通常意味着有一边更新了、另一边忘了。
    """
    a, b = h2(zh), h2(en)
    assert len(a) == len(b), (
        f"{zh.name} 有 {len(a)} 个一级标题，{en.name} 有 {len(b)} 个。\n"
        f"中文：{[x[3:] for x in a]}\n英文：{[x[3:] for x in b]}"
    )


def test_docs_index_pairs_are_real():
    """docs/README.md 里列出的中英文对照，两端都必须存在。"""
    idx = ROOT / "docs" / "README.md"
    text = idx.read_text(encoding="utf-8")
    targets = re.findall(r"\]\(\./?([^)]+)\)", text)
    assert targets, "文档地图里没有任何链接，说明它没被维护"
    for t in targets:
        assert (idx.parent / t).exists() or (ROOT / t).exists(), f"文档地图指向了不存在的 {t}"


def test_docs_index_lists_every_pair():
    """新增一份双语文档，必须同时出现在文档地图里 —— 否则没人找得到它。"""
    text = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    for zh, en in PAIRS:
        if zh.parent != ROOT / "docs":
            continue
        assert zh.name in text, f"{zh.name} 没进文档地图"
        assert en.name in text, f"{en.name} 没进文档地图"


def test_language_switch_links_resolve():
    """每份文档顶部的语言切换链接必须真的指到对方。"""
    for zh, en in PAIRS:
        zt = zh.read_text(encoding="utf-8")
        et = en.read_text(encoding="utf-8")
        assert en.name in zt, f"{zh.name} 里没有指向 {en.name} 的链接"
        assert zh.name in et, f"{en.name} 里没有指向 {zh.name} 的链接"


def test_principles_red_lines_are_counted():
    """原则文档的「反面清单」必须是可数的条目 —— 不能写成一段散文。

    这条测试存在的原因：这份清单是要在 PR 里逐条过的，写成段落就没人会过。
    """
    zh = (ROOT / "docs" / "PRINCIPLES.md").read_text(encoding="utf-8")
    en = (ROOT / "docs" / "PRINCIPLES_EN.md").read_text(encoding="utf-8")
    zh_items = re.search(r"## 反面清单.*?\n(.*?)\n---", zh, re.S)
    en_items = re.search(r"## Red lines.*?\n(.*?)\n---", en, re.S)
    assert zh_items and en_items, "没找到反面清单"
    n_zh = len(re.findall(r"^- ", zh_items.group(1), re.M))
    n_en = len(re.findall(r"^- ", en_items.group(1), re.M))
    assert n_zh >= 8, f"清单只有 {n_zh} 条，太短了"
    assert n_zh == n_en, f"中文 {n_zh} 条、英文 {n_en} 条，两边不一致"
