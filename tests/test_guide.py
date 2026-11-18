#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""引导层契约测试。

`guide/` 是给人看的手册。手册最典型的失效方式不是写错字，是**和实现脱节**——
三个月后 schema 多了一个字段、少了一个枚举值，手册还在讲老规矩，读者照着填，
编译报错，然后手册就没人信了。

所以这里守四件事：

1. **文件齐** —— 目录表里列出的每一份都必须存在
2. **链接可达** —— 文档之间指来指去的相对路径必须真的落地
3. **示例合法** —— `03-SPEC.md` 里的 YAML 示例必须过 `specsheet.schema.json`，
   这一条是整套测试里唯一能证明「手册写的东西真的能跑」的
4. **取值一致** —— 手册里出现的枚举（成色、基元、交付档、受众）必须与 schema 同源

跑法：python3 -m pytest tests/test_guide.py -q
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "guide"
SCHEMA_PATH = ROOT / "spec" / "schema" / "specsheet.schema.json"

# 目录表里承诺的文件，一个都不能少
EXPECTED = [
    "README.md",
    "01-BRIEF.md",
    "02-DECODE.md",
    "03-SPEC.md",
    "04-VERIFY.md",
    "05-DIAGNOSE.md",
    "06-EXPERIENCE.md",
    "WALKTHROUGH.md",
]


def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def md_files() -> list[Path]:
    return sorted(GUIDE.glob("*.md"))


# ── 1. 文件齐 ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("name", EXPECTED)
def test_guide_file_exists(name: str):
    p = GUIDE / name
    assert p.is_file(), f"guide/ 缺 {name}"
    assert p.stat().st_size > 1500, f"{name} 只有 {p.stat().st_size} 字节，像是占位文件"


def test_readme_index_lists_every_file():
    """README 的目录表必须列全，否则新文件等于不存在。"""
    text = (GUIDE / "README.md").read_text(encoding="utf-8")
    for name in EXPECTED:
        if name == "README.md":
            continue
        assert name in text, f"{name} 没进 guide/README.md 的目录表"


# ── 2. 链接可达 ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("path", md_files(), ids=lambda p: p.name)
def test_internal_links_resolve(path: Path):
    """文档里的相对链接必须落地。

    只查相对路径：外链会随网络环境失效，那不该让测试变红。
    """
    text = path.read_text(encoding="utf-8")
    for target in re.findall(r"\]\((\.{1,2}/[^)#]+)\)", text):
        resolved = (path.parent / target).resolve()
        assert resolved.exists(), f"{path.name} 指向了不存在的 {target}"


# ── 3. 示例合法（最重要的一条）──────────────────────────────────────────


def yaml_blocks(path: Path) -> list[str]:
    return re.findall(r"```yaml\n(.*?)```", path.read_text(encoding="utf-8"), re.S)


def test_spec_example_passes_schema():
    """03-SPEC.md 里那份「最小可编译」的示例，必须真的能被 schema 接受。

    这一条存在的理由：手册承诺「复制这份，改掉内容就能跑」。
    如果示例本身不合法，这个承诺就是假的，而读者会在第一次尝试时就撞墙。

    依赖缺失时**直接失败，不跳过**：在 CI 里，跳过和通过长得一模一样，
    而这条恰恰是唯一能证明「手册里写的东西真的能跑」的用例。
    """
    if yaml is None or jsonschema is None:
        pytest.fail(
            "缺 pyyaml 或 jsonschema。装一下：pip install -r tests/requirements.txt\n"
            "这条测试不能静默跳过 —— 跳过与通过在这里长得一样。"
        )

    blocks = yaml_blocks(GUIDE / "03-SPEC.md")
    full = [b for b in blocks if "spec_version" in b and "parts:" in b]
    assert full, "03-SPEC.md 里找不到完整的 SpecSheet 示例"

    for i, block in enumerate(full):
        doc = yaml.safe_load(block)
        try:
            jsonschema.validate(doc, schema())
        except jsonschema.ValidationError as e:  # pragma: no cover
            pytest.fail(f"第 {i + 1} 个 YAML 示例不合法：{e.message}\n路径：{list(e.absolute_path)}")


def test_walkthrough_yaml_is_parseable():
    """WALKTHROUGH 里的 intent 片段至少要是合法 YAML。

    它不完整（只有 intent），所以不校验 schema，但语法必须对——
    读者会复制它。
    """
    if yaml is None:
        pytest.fail("缺 pyyaml，装一下：pip install -r tests/requirements.txt")
    for block in yaml_blocks(GUIDE / "WALKTHROUGH.md"):
        yaml.safe_load(block)


# ── 4. 取值一致 ──────────────────────────────────────────────────────────


def test_audience_enum_matches_schema():
    """手册里讲的受众三档，必须与 schema 的 `intent.audience` 同源。

    写错过一次：初稿写「无基础 / 同行」，schema 里是「外行 / 专业」。
    """
    allowed = set(schema()["properties"]["intent"]["properties"]["audience"]["enum"])
    text = (GUIDE / "01-BRIEF.md").read_text(encoding="utf-8")
    found = set(re.findall(r"\| `([^`]+)` \|", text))
    assert allowed <= found, (
        f"01-BRIEF.md 的受众表缺了 schema 里的取值：{allowed - found}\n"
        f"schema 允许：{sorted(allowed)}，文中出现：{sorted(found)}"
    )


def test_part_kind_matches_schema():
    """五种几何能力在文中列出的 kind，必须与 schema 的 `parts[].kind` 同源。"""
    allowed = set(schema()["properties"]["parts"]["items"]["properties"]["kind"]["enum"])
    text = (GUIDE / "03-SPEC.md").read_text(encoding="utf-8")
    for kind in allowed:
        assert f"`{kind}`" in text, f"03-SPEC.md 没讲 kind: {kind}"
    # 反面：文中要明确说明「孔不是独立基元」
    assert "不是独立基元" in text or "不是独立" in text, (
        "03-SPEC.md 必须说清 hole 是 extrude 的参数而非 kind，否则读者会写 kind: hole"
    )


def test_evidence_grade_matches_schema():
    """三档成色的词必须与 schema 完全一致，一个都不能多。"""
    allowed = set(
        schema()["properties"]["parts"]["items"]["properties"]["evidence"]
        ["additionalProperties"]["properties"]["grade"]["enum"]
    )
    text = (GUIDE / "02-DECODE.md").read_text(encoding="utf-8")
    found = set(re.findall(r"`(measured|inferred|standard)`", text))
    assert allowed == found, f"成色词不一致：schema={sorted(allowed)}，文中={sorted(found)}"
    assert "没有第四种" in text, "02-DECODE.md 必须明确「没有第四种成色」这条硬约束"


def test_delivery_tiers_match_schema():
    allowed = set(schema()["properties"]["intent"]["properties"]["delivery"]["enum"])
    text = (GUIDE / "01-BRIEF.md").read_text(encoding="utf-8")
    for tier in allowed:
        assert f"`{tier}`" in text, f"01-BRIEF.md 没讲交付档 {tier}"


# ── 5. 结构与纪律 ────────────────────────────────────────────────────────


@pytest.mark.parametrize("path", md_files(), ids=lambda p: p.name)
def test_each_file_has_h1(path: Path):
    lines = path.read_text(encoding="utf-8").splitlines()
    assert any(ln.startswith("# ") for ln in lines[:5]), f"{path.name} 前 5 行里没有一级标题"


@pytest.mark.parametrize("path", md_files(), ids=lambda p: p.name)
def test_no_unfilled_placeholders(path: Path):
    """不能留 TODO / {{槽位}} / XXX。

    槽位是原始案例包里的写法（给 AI 的模板），给人看的手册必须把槽位填成例子，
    否则读者不知道该填什么、填到什么程度。
    """
    text = path.read_text(encoding="utf-8")
    for bad in ("TODO", "FIXME", "XXX", "{{"):
        assert bad not in text, f"{path.name} 里残留占位符 {bad}"


def test_verify_has_three_groups():
    """验收门禁必须分组，且 A 组是「不过就不交付」。

    这条测试守的不是格式，是判断：一条平铺的 18 条清单，用起来会退化成
    「扫一眼，都差不多，交吧」。分组给出了拒绝交付的理由。
    """
    text = (GUIDE / "04-VERIFY.md").read_text(encoding="utf-8")
    assert "A 组" in text and "B 组" in text and "C 组" in text
    assert "有一条不过就不交付" in text


def test_diagnose_codes_are_unique():
    """故障码不能重复。重复的码意味着两个不同的根因共用一个名字，诊断就失效了。"""
    text = (GUIDE / "05-DIAGNOSE.md").read_text(encoding="utf-8")
    codes = re.findall(r"`([A-Z]{3,4}-\d{3})`", text)
    assert len(codes) >= 12, f"故障码只有 {len(codes)} 个，太少了"
    dupes = {c for c in codes if codes.count(c) > 1}
    assert not dupes, f"故障码重复：{sorted(dupes)}"


def test_diagnose_keeps_the_rule():
    """诊断纪律那句「不倒推代码，倒推系统」必须留着——它是这一章的方法论前提。"""
    text = (GUIDE / "05-DIAGNOSE.md").read_text(encoding="utf-8")
    assert "倒推系统" in text
