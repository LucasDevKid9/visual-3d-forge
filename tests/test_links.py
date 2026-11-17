"""链接与清单一致性。

README 是唯一一个所有访客都会读、却几乎没人会验证的文件。
所以这里的每条相对链接、每张图片、每个 workflow 文件都必须被机器检查一遍。

覆盖：
1. Markdown 相对链接与图片目标存在
2. workflow YAML 可解析，且没有引用不存在的脚本
3. 仓库根的关键文件齐全（开源仓库的「门面六件套」）
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MD_FILES = [
    ROOT / "README.md",
    ROOT / "README_EN.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "SECURITY.md",
    ROOT / "CODE_OF_CONDUCT.md",
    ROOT / "CHANGELOG.md",
    *sorted((ROOT / "docs").glob("*.md")),
]

LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HTML_RE = re.compile(r'(?:src|href)="([^"]+)"')


def iter_links(text: str):
    for m in LINK_RE.finditer(text):
        yield m.group(1)
    for m in HTML_RE.finditer(text):
        yield m.group(1)


def is_external(url: str) -> bool:
    return url.startswith(("http://", "https://", "#", "mailto:", "data:"))


@pytest.mark.parametrize("md", MD_FILES, ids=lambda p: p.name)
def test_相对链接都指向真实文件(md: Path) -> None:
    assert md.is_file(), f"文档缺失：{md.name}"
    broken = []
    for url in iter_links(md.read_text(encoding="utf-8")):
        if is_external(url):
            continue
        target = (md.parent / url.split("#")[0]).resolve()
        if not target.exists():
            broken.append(url)
    assert not broken, f"{md.name} 有断链：{broken}"


def test_两个_README_的章节对得上() -> None:
    zh = (ROOT / "README.md").read_text(encoding="utf-8")
    en = (ROOT / "README_EN.md").read_text(encoding="utf-8")
    # 中英版本不必逐句对应，但结构不能一边有、一边没有
    assert zh.count("\n## ") == en.count("\n## "), (
        f"章节数不一致：中文 {zh.count('## ')} / 英文 {en.count('## ')}"
    )


def test_workflow_可解析() -> None:
    yaml = pytest.importorskip("yaml")
    wf_dir = ROOT / ".github" / "workflows"
    files = sorted(wf_dir.glob("*.yml"))
    assert len(files) >= 3, "至少要有 ci / pages / release 三条流水线"
    for f in files:
        doc = yaml.safe_load(f.read_text(encoding="utf-8"))
        assert "jobs" in doc, f"{f.name} 没有 jobs"
        # YAML 1.1 把裸写的 on 解析成布尔 True —— 不是 workflow 的错，是解析器的
        assert ("on" in doc) or (True in doc), f"{f.name} 没有触发条件"


def test_workflow_引用的脚本存在() -> None:
    yaml = pytest.importorskip("yaml")
    missing = []
    for f in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        text = f.read_text(encoding="utf-8")
        for rel in re.findall(r"python3? (scripts/[\w./-]+\.py)", text):
            if not (ROOT / rel).is_file():
                missing.append(f"{f.name}: {rel}")
    assert not missing, f"workflow 引用了不存在的脚本：{missing}"


@pytest.mark.parametrize("name", ["LICENSE", "README.md", "README_EN.md", "SKILL.md",
                                  "CONTRIBUTING.md", "SECURITY.md", "CODE_OF_CONDUCT.md",
                                  "CHANGELOG.md", "THIRD-PARTY-NOTICES.md"])
def test_门面文件齐全(name: str) -> None:
    assert (ROOT / name).is_file(), f"缺少 {name}"
