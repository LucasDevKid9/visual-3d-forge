#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""references/ 的编号契约。

`references/` 用 `NN-kebab-name.md` 编号。编号不是装饰——文档之间靠它互相指，
SKILL.md 靠它建索引，读者靠它判断「该先读哪几篇」。

重编号（比如插一篇新文档）最容易出的错不是漏改名，是**改了文件名、没改引用**：
读者点 `12-api-verification.md` 会 404，而写的人完全不知道。

所以这里守四件事：

1. 编号从 00 连续，无重复、无空号
2. 每个文件的一级标题带自己的编号（`# 16 · R3F 轨道`）
3. SKILL.md 的索引列出了每一个文件
4. 文档里引用的 `NN-xxx.md` 必须存在

跑法：python3 -m pytest tests/test_references.py -q
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
REFS = ROOT / "references"
SKILL = ROOT / "SKILL.md"

FILES = sorted(p for p in REFS.glob("*.md"))
NUMS = [int(p.name[:2]) for p in FILES if p.name[:2].isdigit()]


def test_numbering_is_contiguous():
    """编号必须 00,01,02… 连续。

    缺号通常意味着删过一篇但没补；重号意味着插了一篇但没挪后面的。
    两种都会让「按编号找文档」这件事失效。
    """
    assert NUMS, "references/ 下没有编号文件"
    assert NUMS == list(range(len(NUMS))), (
        f"编号不连续：{NUMS}\n"
        f"期望 {list(range(len(NUMS)))}"
    )


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_title_carries_its_number(path: Path):
    """一级标题必须带自己的编号。

    不带编号的标题，人在正文里跳转时会失去位置感；
    从别处拷进来的文档尤其容易忘（它原本没有编号）。
    """
    num = path.name[:2]
    head = path.read_text(encoding="utf-8").splitlines()
    h1 = next((ln for ln in head[:8] if ln.startswith("# ")), None)
    assert h1, f"{path.name} 前 8 行没有一级标题"
    assert num in h1, f"{path.name} 的标题没带编号：{h1}"


def test_skill_index_lists_every_reference():
    """SKILL.md 的文件索引必须列出每一个 reference。

    没进索引的文件，等于只对知道它存在的人存在。
    """
    text = SKILL.read_text(encoding="utf-8")
    missing = [p.name for p in FILES if p.name not in text]
    assert not missing, f"SKILL.md 的索引漏了：{missing}"


def test_all_reference_links_resolve():
    """文档里引用的 `NN-xxx.md` 必须真的存在。

    这条是重编号的护栏：改了文件名没改引用的那种错，只有它能抓。
    """
    broken = []
    for p in list(FILES) + [SKILL, ROOT / "README.md", ROOT / "README_EN.md"]:
        text = p.read_text(encoding="utf-8")
        for ref in set(re.findall(r"(\d{2}-[a-z0-9-]+\.md)", text)):
            if not (REFS / ref).exists():
                broken.append(f"{p.name} → {ref}")
    assert not broken, "引用了不存在的 reference：\n" + "\n".join(broken)


def test_experience_docs_are_marked_not_for_confirmdeliverable():
    """四篇体验文档必须能被一眼辨认为「不是确认件主线」。

    原因：确认件是展示型（见 guide/06-EXPERIENCE.md）。这四篇是给体验型/混合型用的，
    如果读者误以为它们是必读，就会给一份要签字的工程文件加音效和结算页。
    """
    exp = [p for p in FILES if p.name[:2] in ("18", "19", "20", "21")]
    assert len(exp) == 4, f"体验四篇不全：{[p.name for p in exp]}"
    for p in exp:
        text = p.read_text(encoding="utf-8")
        assert "展示型" in text or "体验型" in text, (
            f"{p.name} 没有说明它服务于哪种产物类型"
        )
