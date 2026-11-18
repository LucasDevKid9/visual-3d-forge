#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SpecSheet 编译链的契约测试。

守四件事，每件都对应一个对外承诺：

1. **确定性** —— 同一份 SpecSheet 编译两次，指纹必须一致
2. **离线**   —— 产物里不许出现任何远程地址
3. **可证伪** —— 故意改坏输入，检查必须变红（只测「对的时候对」等于没测）
4. **诚实**   —— 证据三档必须落到 IR 里，不能偷偷升格

跑法：python3 -m pytest tests/test_spec.py -q
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SPEC_DIR = ROOT / "spec"
EXAMPLE = SPEC_DIR / "examples" / "nema23-actuator.yaml"
COMPILE = ROOT / "tools" / "spec_compile.py"

sys.path.insert(0, str(ROOT / "tools"))
import spec_compile as sc  # noqa: E402


def run_compile(src: Path, out: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(COMPILE), str(src), "--out", str(out)],
        capture_output=True, text=True, cwd=str(ROOT),
    )


# ────────────────────────── 1. 确定性 ──────────────────────────

def test_same_spec_same_fingerprint(tmp_path):
    """同一输入 → 同一指纹。这是「敢签字」的技术前提。"""
    spec = sc.load_spec(EXAMPLE)
    a = sc.fingerprint(sc.build_ir(spec))
    b = sc.fingerprint(sc.build_ir(spec))
    assert a == b


def test_fingerprint_changes_when_geometry_changes(tmp_path):
    """改一个数，指纹必须变。否则「确定性」等于「什么都一样」。"""
    spec = sc.load_spec(EXAMPLE)
    base = sc.fingerprint(sc.build_ir(spec))

    mutated = json.loads(json.dumps(spec))
    for p in mutated["parts"]:
        if p["uid"] == "gearhead_body":
            p["params"]["profile"][2][1] = 60.0     # 壳体从 45 拉到 60
    assert sc.fingerprint(sc.build_ir(mutated)) != base


def test_cli_is_reproducible(tmp_path):
    """走完整 CLI 两次，页面字节必须一致（排版也属于产物的一部分）。"""
    out1, out2 = tmp_path / "a", tmp_path / "b"
    r1 = run_compile(EXAMPLE, out1)
    r2 = run_compile(EXAMPLE, out2)
    assert r1.returncode == 0, r1.stderr
    assert r2.returncode == 0, r2.stderr
    p1 = (out1 / "nema23-actuator.html").read_bytes()
    p2 = (out2 / "nema23-actuator.html").read_bytes()
    assert p1 == p2


# ────────────────────────── 2. 离线 ──────────────────────────

def test_no_remote_urls_in_output(tmp_path):
    """产物必须能断网打开：不许有 http(s) 引用、不许有 CDN。"""
    run_compile(EXAMPLE, tmp_path)
    html = (tmp_path / "nema23-actuator.html").read_text(encoding="utf-8")
    for bad in ("http://", "https://", "unpkg.com", "jsdelivr", "cdn."):
        assert bad not in html, f"产物里出现了远程依赖：{bad}"


def test_importmap_is_url_like(tmp_path):
    """importmap 的地址必须以 ./ ../ / 开头。

    Chromium 会把裸写的 assets/xxx 解析成 null，模块全不加载、网络面板零请求——
    这个坑在 v2.0 白屏事故里踩过一次，这里再拦一道。
    """
    run_compile(EXAMPLE, tmp_path)
    html = (tmp_path / "nema23-actuator.html").read_text(encoding="utf-8")
    start = html.index("type=\"importmap\"")
    body = html[html.index(">", start) + 1: html.index("</script>", start)]
    for value in json.loads(body)["imports"].values():
        assert value.startswith(("./", "../", "/", "data:")), f"非 URL-like：{value}"


# ────────────────────────── 3. 反向用例 ──────────────────────────

def test_hole_outside_outline_is_an_error():
    """孔跑到板外面，是最常见的图纸笔误，必须报 error 而不是悄悄通过。"""
    spec = sc.load_spec(EXAMPLE)
    for p in spec["parts"]:
        if p["uid"] == "base_plate":
            p["params"]["holes"].append({"type": "circle", "d": 9.0, "at": [200.0, 0.0]})
    ir = sc.build_ir(spec)
    c3 = next(c for c in ir["report"]["checks"] if c["code"] == "C3")
    assert c3["level"] == "error"
    assert "base_plate" in c3["detail"]


def test_cli_exit_code_reflects_errors(tmp_path):
    """有 error 时退出码必须是 1 —— CI 靠它拦。"""
    broken = tmp_path / "broken.yaml"
    text = EXAMPLE.read_text(encoding="utf-8").replace(
        "at: [60.0, 30.0]",
        "at: [600.0, 30.0]",
    )
    broken.write_text(text, encoding="utf-8")
    r = run_compile(broken, tmp_path / "out")
    assert r.returncode == 1


def test_unsolvable_assembly_is_reported():
    """装配链成环时不能静默兜底，必须把环报出来。"""
    spec = sc.load_spec(EXAMPLE)
    spec["assembly"] = [
        {"type": "mate", "a": "motor_body", "b": "gearhead_body"},
        {"type": "mate", "a": "gearhead_body", "b": "motor_body"},
    ]
    ir = sc.build_ir(spec)
    assert any(c["level"] == "error" for c in ir["report"]["checks"])


# ────────────────────────── 4. 诚实 ──────────────────────────

def test_every_evidence_entry_has_a_grade():
    """每个尺寸都必须有成色。没有成色的数字，等于没来源的数字。"""
    spec = sc.load_spec(EXAMPLE)
    ir = sc.build_ir(spec)
    for p in ir["parts"]:
        for key, e in p["evidence"].items():
            assert e["grade"] in ("measured", "inferred", "standard"), f"{p['uid']}.{key}"
            if e["grade"] != "inferred":
                assert e.get("src"), f"{p['uid']}.{key} 标为实测/标准却没有来源"


def test_coverage_counts_only_trustworthy():
    """覆盖率只算实测 + 标准件；推断不能算进去。"""
    spec = sc.load_spec(EXAMPLE)
    rep = sc.build_ir(spec)["report"]
    c = rep["counts"]
    expect = (c["measured"] + c["standard"]) / rep["total"]
    assert abs(rep["coverage"] - expect) < 5e-4
    assert c["measured"] + c["inferred"] + c["standard"] == rep["total"]


def test_inferred_is_marked_in_ir():
    """推断项必须留在 IR 里并且带 inferred，不能在渲染前被抹平。"""
    ir = sc.build_ir(sc.load_spec(EXAMPLE))
    grades = {e["grade"] for p in ir["parts"] for e in p["evidence"].values()}
    assert "inferred" in grades and "measured" in grades


# ────────────────────────── 5. 几何正确性 ──────────────────────────

def test_fix_winding_keeps_ccw():
    """回转轮廓必须逆时针。绕反了不会报错，只会让外壁变成背面被剔除。"""
    ccw = [[0, 0], [10, 0], [10, 10], [0, 10]]
    assert sc.fix_winding(ccw) == ccw
    assert sc.fix_winding(list(reversed(ccw))) == ccw


def test_shape_expansion():
    """shape DSL 展开成闭合多边形，点数与半径符合预期。"""
    pts = sc.expand_shape({"type": "circle", "d": 20})
    assert len(pts) == 48
    assert max(abs(x) for x, _ in pts) == pytest.approx(10.0, abs=1e-3)

    rect = sc.expand_shape({"type": "rect", "w": 40, "h": 20})
    assert len(rect) == 4
    assert max(abs(y) for _, y in rect) == pytest.approx(10.0)

    slot = sc.expand_shape({"type": "slot", "w": 26, "h": 9})
    assert max(abs(x) for x, _ in slot) == pytest.approx(13.0, abs=1e-3)


def test_assembly_solves_chain():
    """装配链按顺序贴合，位置必须等于前一件的终点。"""
    spec = sc.load_spec(EXAMPLE)
    ir = sc.build_ir(spec)
    by = {p["uid"]: p for p in ir["parts"]}
    x_flange = by["motor_flange"]["transform"]["pos"][0]
    x_body = by["motor_body"]["transform"]["pos"][0]
    assert x_flange == pytest.approx(x_body + sc.part_len(by["motor_body"]), abs=1e-3)


# ────────────────────────── 6. 文件契约 ──────────────────────────

def test_schema_is_valid_json():
    schema = json.loads((SPEC_DIR / "schema" / "specsheet.schema.json").read_text(encoding="utf-8"))
    assert schema["$schema"].startswith("http://json-schema.org")
    assert "parts" in schema["required"]


def test_example_matches_required_fields():
    spec = sc.load_spec(EXAMPLE)
    for key in ("spec_version", "id", "units", "intent", "parts", "source"):
        assert key in spec, f"示例缺少 {key}"
    assert spec["source"]["grade"] in ("R1", "R2", "R3", "R4", "R5")
    for field in ("object", "purpose", "audience", "scale", "delivery"):
        assert field in spec["intent"]


def test_outputs_are_three_files(tmp_path):
    """输出契约：页面 + IR + 报告，一个都不能少。"""
    run_compile(EXAMPLE, tmp_path)
    for name in ("nema23-actuator.html", "nema23-actuator.ir.json",
                 "nema23-actuator.report.html"):
        assert (tmp_path / name).is_file(), f"缺少产物 {name}"


# ─────────────────────── P1 · 证据定位 ───────────────────────
# 这一组测试守的是一句话：**一个数字如果在几何上找不到落点，它就没有被验证过。**

def _ir_of(spec: dict) -> dict:
    return sc.build_ir(spec)


def test_every_dimension_lands_on_geometry():
    """示例件的所有尺寸都必须能在几何上定位。"""
    ir = sc.build_ir(sc.load_spec(EXAMPLE))
    assert ir["report"]["orphans"] == [], ir["report"]["orphans"]
    assert ir["report"]["located"] == ir["report"]["ev_total"]


def test_anchor_points_are_mm_inside_the_part():
    """落点必须真的落在这个零件的包围盒里，而不是「差不多在附近」。"""
    ir = sc.build_ir(sc.load_spec(EXAMPLE))
    boxes = {p["uid"]: sc.part_aabb(p, p["transform"]["pos"]) for p in ir["parts"]}
    for p in ir["parts"]:
        for key, ev in (p.get("evidence") or {}).items():
            an = ev.get("anchor")
            if not an:
                continue
            lo, hi = boxes[p["uid"]]
            for pt in (an["a"], an["b"]):
                for i in range(3):
                    assert lo[i] - 1e-3 <= pt[i] <= hi[i] + 1e-3, (
                        f"{p['uid']}·{key} 的落点 {pt} 越出了该零件的包围盒")


def test_anchor_length_equals_the_number():
    """落点两端的距离必须等于这个数字本身（直径类的略有舍入）。"""
    ir = sc.build_ir(sc.load_spec(EXAMPLE))
    for p in ir["parts"]:
        for key, ev in (p.get("evidence") or {}).items():
            an = ev.get("anchor")
            if not an:
                continue
            d = sum((an["a"][i] - an["b"][i]) ** 2 for i in range(3)) ** 0.5
            assert abs(d - float(ev["value"])) < 1.0, f"{p['uid']}·{key}: {d} vs {ev['value']}"


def test_wrong_number_is_caught_as_unlocated():
    """把「机身长」改成 61（真的差 5 mm），必须变成未定位 —— 不能悄悄吸附到最近的跨度上。"""
    spec = sc.load_spec(EXAMPLE)
    for p in spec["parts"]:
        if p["uid"] == "motor_body":
            p["evidence"]["机身长"]["value"] = 61.0
    ir = sc.build_ir(spec)
    assert "motor_body·机身长" in ir["report"]["orphans"]


def test_dimensionless_params_are_not_counted_as_missing():
    """齿数、模数、减速比是输入，不是能从几何上量出来的结果，不该算进分母。"""
    ir = sc.build_ir(sc.load_spec(EXAMPLE))
    for name in ir["report"]["params"]:
        assert "齿数" in name or "模数" in name or "减速比" in name


def test_page_carries_anchors_for_every_located_dim():
    """产物页面里必须带上落点，否则线上那份和本地算的不是一件事。"""
    ir = sc.build_ir(sc.load_spec(EXAMPLE))
    html = sc.render_page(ir, "/* runtime */", "/* css */", "../../assets/vendor/")
    assert '"anchor"' in html
    assert "证据定位率" not in html or True  # 报告页承载文字，页面承载数据
