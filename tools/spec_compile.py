#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spec_compile.py — 把 SpecSheet 编译成一个确认页
================================================
    python3 tools/spec_compile.py spec/examples/nema23-actuator.yaml --out spec/out/

三件事，按顺序，每一步都可以被单独测试：

    ① 展开    把 shape DSL（rect / circle / slot）变成多边形顶点 —— 纯函数
    ② 求解    把「装配关系」变成「世界坐标」—— 拓扑序 + 迭代收敛
    ③ 检查    尺度自洽 / 贴合 / 孔位 / 干涉 / 证据覆盖率 —— 产出可对外出示的报告

它不调用任何模型。同一个 SpecSheet 进来，永远同一个 IR、同一个哈希出去。
这是这个项目的全部主张：**能复现的，才敢签字。**

退出码：0 全部通过（可含 warning）；1 存在 error；2 输入不可读或不合法。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "spec" / "runtime" / "viewer.js"
STYLE = ROOT / "spec" / "runtime" / "viewer.css"

GRADE_LABEL = {"measured": "实测", "inferred": "推断", "standard": "标准"}


# ────────────────────────────── 基础 ──────────────────────────────

def die(msg: str, code: int = 2) -> None:
    print(f"[spec] {msg}", file=sys.stderr)
    sys.exit(code)


def load_spec(path: Path) -> dict:
    if not path.is_file():
        die(f"找不到 SpecSheet：{path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError:
            die("读取 YAML 需要 PyYAML：pip install pyyaml")
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        die("SpecSheet 顶层必须是对象")
    for key in ("id", "units", "parts", "intent"):
        if key not in data:
            die(f"缺少必填字段：{key}")
    return data


# ────────────────────────────── ① 展开 ──────────────────────────────

def circle_pts(d: float, n: int = 48) -> list[list[float]]:
    r = d / 2.0
    return [[round(r * math.cos(2 * math.pi * i / n), 4),
             round(r * math.sin(2 * math.pi * i / n), 4)] for i in range(n)]


def rect_pts(w: float, h: float) -> list[list[float]]:
    x, y = w / 2.0, h / 2.0
    return [[-x, -y], [x, -y], [x, y], [-x, y]]


def slot_pts(w: float, h: float, n: int = 16) -> list[list[float]]:
    """长圆孔：两端半圆 + 两条直边。"""
    r = h / 2.0
    cx = max(w / 2.0 - r, 0.0)
    pts: list[list[float]] = []
    for i in range(n + 1):                     # 右半圆
        a = -math.pi / 2 + math.pi * i / n
        pts.append([cx + r * math.cos(a), r * math.sin(a)])
    for i in range(n + 1):                     # 左半圆
        a = math.pi / 2 + math.pi * i / n
        pts.append([-cx + r * math.cos(a), r * math.sin(a)])
    return [[round(p[0], 4), round(p[1], 4)] for p in pts]


def expand_shape(s) -> list[list[float]]:
    """把 shape DSL 展开成多边形顶点，并应用 `at` 偏移。

    `at` 曾经被漏掉过：所有孔都堆在原点，C3「孔位在轮廓内」因此永远通过——
    检查项看着是绿的，其实是没测到。**静默忽略字段比报错危险得多。**
    """
    if isinstance(s, list):
        pts = [[float(p[0]), float(p[1])] for p in s]
    else:
        t = s.get("type")
        if t == "circle":
            pts = circle_pts(float(s["d"]))
        elif t == "rect":
            pts = rect_pts(float(s["w"]), float(s["h"]))
        elif t == "slot":
            pts = slot_pts(float(s["w"]), float(s["h"]))
        else:
            die(f"未知的轮廓类型：{t}")

    if isinstance(s, dict) and s.get("at"):
        dx, dy = float(s["at"][0]), float(s["at"][1])
        pts = [[x + dx, y + dy] for x, y in pts]
    return pts


def fix_winding(profile: list[list[float]]) -> list[list[float]]:
    """回转轮廓的绕向决定法线朝向。

    Lathe 按点的顺序生成面，逆时针（在 r–a 平面上）才朝外。
    绕反了不会报错，只会让外壁变成背面而被剔除——看到的其实是远侧内壁，
    表现为莫名其妙的斜向条带。**这类错误必须死在编译期，不能靠肉眼在浏览器里找。**
    """
    area = 0.0
    n = len(profile)
    for i in range(n):
        x1, y1 = profile[i]
        x2, y2 = profile[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return list(reversed(profile)) if area < 0 else profile


def expand_part(p: dict) -> dict:
    """把 DSL 展开成运行时能直接吃的低级参数。展开后 IR 里不再有 DSL。"""
    out = dict(p)
    params = dict(p.get("params") or {})
    kind = p["kind"]

    if kind == "extrude":
        params["outline"] = expand_shape(params["outline"])
        params["holes"] = [expand_shape(h) for h in (params.get("holes") or [])]
    elif kind == "pattern":
        proto = dict(params["proto"])
        proto["params"] = expand_part({"kind": proto["kind"], "params": proto["params"]})["params"]
        params["proto"] = proto
    elif kind == "revolve":
        params["profile"] = fix_winding([[float(r), float(a)] for r, a in params["profile"]])

    out["params"] = params
    out.setdefault("axis", "x")
    out.setdefault("material", "steel")
    out.setdefault("internal", False)
    out.setdefault("evidence", {})
    out.setdefault("explode", [0, 0, 0])
    return out


# ────────────────────────────── ② 求解 ──────────────────────────────

def part_len(p: dict) -> float:
    """沿主轴的长度。基元约定：从 0 长到 L。"""
    k, pr = p["kind"], p["params"]
    if k == "revolve":
        return max(a for _, a in pr["profile"]) - min(a for _, a in pr["profile"])
    if k == "extrude":
        return float(pr["depth"])
    if k == "gear":
        return float(pr["thickness"])
    if k == "pattern":
        return part_len({"kind": pr["proto"]["kind"], "params": pr["proto"]["params"]})
    return 0.0


def part_half(p: dict) -> tuple[float, float, float]:
    """世界坐标下三个轴的半尺寸。用于包围盒、干涉与相机拟合。"""
    k, pr, ax = p["kind"], p["params"], p.get("axis", "x")
    L = part_len(p)

    if k == "revolve":
        r = max(x for x, _ in pr["profile"])
        h = {"x": (L / 2, r, r), "y": (r, L / 2, r), "z": (r, r, L / 2)}[ax]
        return h
    if k == "gear":
        r = pr["m"] * pr["z"] / 2.0 + pr["m"]
        h = {"x": (L / 2, r, r), "y": (r, L / 2, r), "z": (r, r, L / 2)}[ax]
        return h
    if k == "extrude":
        pts = pr["outline"]
        hx = max(abs(x) for x, _ in pts)
        hy = max(abs(y) for _, y in pts)
        if ax == "x":
            return (L / 2, hy, hx)
        if ax == "y":
            return (hx, L / 2, hy)
        return (hx, hy, L / 2)
    if k == "pattern":
        proto = {"kind": pr["proto"]["kind"], "params": pr["proto"]["params"], "axis": ax}
        ph = part_half(proto)
        R = float(pr["radius"])
        return (max(ph[0], R), max(ph[1], R), max(ph[2], R))
    return (L / 2, L / 2, L / 2)


def part_center(p: dict) -> list[float]:
    """零件在自身坐标系里的中心（相对 pos）。基元从 0 长到 L，所以是 L/2。"""
    ax, L = p.get("axis", "x"), part_len(p)
    if p["kind"] in ("extrude", "gear") and ax == "y":
        return [0.0, L / 2.0, 0.0]
    if p["kind"] in ("extrude", "gear") and ax == "z":
        return [0.0, 0.0, L / 2.0]
    return [L / 2.0, 0.0, 0.0]


def part_aabb(p: dict, pos: list[float]) -> tuple[list[float], list[float]]:
    h = part_half(p)
    c = part_center(p)
    cx, cy, cz = pos[0] + c[0], pos[1] + c[1], pos[2] + c[2]
    return ([cx - h[0], cy - h[1], cz - h[2]], [cx + h[0], cy + h[1], cz + h[2]])


def solve_assembly(parts: list[dict], constraints: list[dict]) -> tuple[dict, list[str]]:
    """装配链求解。

    两条规则，够了：
      · mate(a, b, offset)  →  a 贴在 b 的 +X 侧，起点 = b 终点 + offset
      · mount {to, at, shift} →  a 挂在 to 的「起点 + at」处，再加 shift

    迭代到稳定（最多 40 轮）。有环会不收敛，直接报出来——不静默兜底。
    """
    lens = {p["uid"]: part_len(p) for p in parts}
    mate_of: dict[str, tuple[str, float]] = {}
    for c in constraints or []:
        if c.get("type") == "mate" and c.get("a") and c.get("b"):
            mate_of[c["a"]] = (c["b"], float(c.get("offset", 0.0)))

    pos = {p["uid"]: [0.0, 0.0, 0.0] for p in parts}
    for _ in range(40):
        changed = False
        for p in parts:
            uid = p["uid"]
            new = list(pos[uid])
            if "mount" in p:
                m = p["mount"]
                base = pos.get(m["to"])
                if base is None:
                    continue
                at = float(m.get("at", 0.0))
                sh = m.get("shift", [0, 0, 0])
                new = [base[0] + at + float(sh[0]),
                       base[1] + float(sh[1]),
                       base[2] + float(sh[2])]
            elif uid in mate_of:
                b, off = mate_of[uid]
                if b not in pos:
                    continue
                new = [pos[b][0] + lens[b] + off, 0.0, 0.0]
            if any(abs(a - b) > 1e-6 for a, b in zip(new, pos[uid])):
                pos[uid] = new
                changed = True
        if not changed:
            return pos, []
    slow = [p["uid"] for p in parts if "mount" in p or p["uid"] in mate_of]
    return pos, [f"装配约束在 40 轮内未收敛，可能有环：{', '.join(slow)}"]


# ────────────────────────────── ③ 检查 ──────────────────────────────

def run_checks(parts, constraints, pos) -> dict:
    checks: list[dict] = []
    by_uid = {p["uid"]: p for p in parts}

    # C1 同轴：声明了 coax 的，横向偏移必须为 0
    bad = []
    for c in constraints or []:
        if c.get("type") == "coax":
            a, b = c.get("a"), c.get("b")
            if a in pos and b in pos:
                dy = abs(pos[a][1] - pos[b][1])
                dz = abs(pos[a][2] - pos[b][2])
                if dy > 0.5 or dz > 0.5:
                    bad.append(f"{a}↔{b} 偏移 Δy={dy:.2f} Δz={dz:.2f}")
    checks.append({
        "code": "C1", "level": "error" if bad else "pass",
        "title": "同轴",
        "detail": "；".join(bad) if bad else "所有 coax 约束的横向偏移为 0（≤0.5 mm）",
    })

    # C2 贴合：mate 的实际间隙
    gaps, worst = [], 0.0
    for c in constraints or []:
        if c.get("type") == "mate":
            a, b = c["a"], c["b"]
            if a not in pos or b not in pos:
                continue
            off = float(c.get("offset", 0.0))
            gap = pos[a][0] - (pos[b][0] + part_len(by_uid[b])) - off
            worst = max(worst, abs(gap))
            if abs(gap) > 0.05:
                gaps.append(f"{a}↔{b} 间隙 {gap:+.3f} mm")
    checks.append({
        "code": "C2", "level": "warn" if gaps else "pass",
        "title": "贴合间隙",
        "detail": "；".join(gaps) if gaps else f"{len([c for c in constraints or [] if c.get('type')=='mate'])} 处贴合，最大偏差 {worst:.3f} mm",
    })

    # C3 孔位在轮廓内：孔越界是最常见的图纸笔误
    over = []
    for p in parts:
        if p["kind"] != "extrude":
            continue
        pts = p["params"]["outline"]
        bx = max(abs(x) for x, _ in pts)
        by = max(abs(y) for _, y in pts)
        for hole in p["params"].get("holes") or []:
            hx = max(abs(x) for x, _ in hole)
            hy = max(abs(y) for _, y in hole)
            if hx > bx + 1e-6 or hy > by + 1e-6:
                over.append(f"{p['uid']} 的孔超出轮廓 {max(hx - bx, hy - by):.1f} mm")
    checks.append({
        "code": "C3", "level": "error" if over else "pass",
        "title": "孔位在轮廓内",
        "detail": "；".join(over) if over else "所有孔洞均落在轮廓内，无越界",
    })

    # C4 干涉：AABB 相交（贴合对与挂载对排除在外）
    allowed = set()
    for c in constraints or []:
        if c.get("type") == "mate":
            allowed.add(tuple(sorted((c["a"], c["b"]))))
    for p in parts:
        if "mount" in p:
            allowed.add(tuple(sorted((p["uid"], p["mount"]["to"]))))
    # 内部件不参与：它们本来就设计在壳体内腔里，AABB 看不出「腔」。
    internal = {p["uid"] for p in parts if p.get("internal")}
    clash = []
    boxes = {p["uid"]: part_aabb(p, pos[p["uid"]]) for p in parts}
    uids = list(boxes)
    for i in range(len(uids)):
        for j in range(i + 1, len(uids)):
            a, b = uids[i], uids[j]
            if a in internal or b in internal:
                continue
            if tuple(sorted((a, b))) in allowed:
                continue
            (a0, a1), (b0, b1) = boxes[a], boxes[b]
            ov = [min(a1[k], b1[k]) - max(a0[k], b0[k]) for k in range(3)]
            if all(v > 1e-6 for v in ov):
                clash.append(f"{a} ⨯ {b}（重叠 {min(ov):.1f} mm）")
    checks.append({
        "code": "C4", "level": "warn" if clash else "pass",
        "title": "包围盒干涉",
        "detail": ("；".join(clash[:4]) + ("…" if len(clash) > 4 else "") if clash
                   else "无未声明干涉（AABB 粗筛；贴合对与内部件已排除）"),
    })

    # C5 证据覆盖率：实测 + 标准件算「可信」，推断不算
    counts = {"measured": 0, "inferred": 0, "standard": 0}
    for p in parts:
        for e in (p.get("evidence") or {}).values():
            counts[e.get("grade", "inferred")] = counts.get(e.get("grade", "inferred"), 0) + 1
    total = sum(counts.values()) or 1
    coverage = (counts["measured"] + counts["standard"]) / total
    level = "pass" if coverage >= 0.6 else "warn"
    checks.append({
        "code": "C5", "level": level,
        "title": "证据覆盖率",
        "detail": f"可信 {coverage*100:.0f}%（实测 {counts['measured']} + 标准 {counts['standard']}）/ 共 {total} 项；"
                  f"推断 {counts['inferred']} 项已在页面以琥珀色标出",
    })

    return {"checks": checks, "coverage": round(coverage, 4), "counts": counts, "total": total}


# ────────────────────────────── 输出 ──────────────────────────────

def build_ir(spec: dict) -> dict:
    parts = [expand_part(dict(p)) for p in spec["parts"]]
    constraints = spec.get("assembly") or []
    pos, notes = solve_assembly(parts, constraints)
    report = run_checks(parts, constraints, pos)

    for p in parts:
        p["transform"] = {"pos": [round(v, 4) for v in pos[p["uid"]]], "rot": [0, 0, 0]}

    ir = {
        "ir_version": "0.1",
        "id": spec["id"],
        "title": spec.get("title") or spec["id"],
        "subtitle": spec.get("subtitle") or "",
        "units": spec["units"],
        "scale": 0.001 if spec["units"] == "mm" else (0.01 if spec["units"] == "cm" else 1.0),
        "grade": (spec.get("source") or {}).get("grade", "R5"),
        "source": spec.get("source") or {},
        "intent": spec["intent"],
        "parts": [{k: v for k, v in p.items() if k != "mount"} for p in parts],
        "views": spec.get("views") or [{"id": "hero", "kind": "iso", "label": "等轴"}],
        "report": report,
    }
    if notes:
        ir["report"]["checks"].append({
            "code": "C0", "level": "error", "title": "装配求解", "detail": "；".join(notes),
        })
    return ir


def fingerprint(ir: dict) -> str:
    """产物指纹：同一份 IR 必须同指纹。这是「确定性」的可验证形式。"""
    payload = json.dumps(ir, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def render_page(ir: dict, runtime: str, css: str, vendor_rel: str) -> str:
    data = json.dumps(ir, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{ir["title"]} · 确认件</title>
<meta name="description" content="{ir["title"]}——由 SpecSheet 编译生成的装配确认件，含证据链与尺寸来源。">
<meta name="generator" content="visual-3d-forge / spec_compile.py">
<style>{css}</style>
</head>
<body>
<script type="importmap">
{{"imports":{{"three":"{vendor_rel}three.module.js","three/addons/":"{vendor_rel}addons/"}}}}
</script>
<script type="module">
window.__IR = {data};
{runtime}
</script>
</body>
</html>
"""


def render_report(ir: dict, fp: str, css: str) -> str:
    rep = ir["report"]
    rows = []
    for c in rep["checks"]:
        rows.append(
            f'<tr class="{c["level"]}"><td class="code">{c["code"]}</td>'
            f'<td class="title">{c["title"]}</td><td class="detail">{c["detail"]}</td>'
            f'<td class="lvl">{ {"pass":"通过","warn":"注意","error":"失败"}[c["level"]] }</td></tr>'
        )
    detail_rows = []
    for p in ir["parts"]:
        for k, e in (p.get("evidence") or {}).items():
            detail_rows.append(
                f'<tr><td>{p["label"]}</td><td>{k}</td>'
                f'<td class="num">{e["value"]}</td>'
                f'<td class="g-{e["grade"]}">{GRADE_LABEL[e["grade"]]}</td>'
                f'<td class="src">{e.get("src") or "—"}</td></tr>'
            )
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{ir["title"]} · 一致性报告</title>
<style>
:root{{--bg:#121110;--ink:#ece7df;--dim:#8f887e;--line:#2e2a26;--ok:#7fbf6a;--warn:#d9a24a;--bad:#c2604f;--acc:#c8a06a;
--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;--sans:-apple-system,"PingFang SC","Noto Sans SC",sans-serif}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);
padding:clamp(24px,5vw,72px);line-height:1.7}}
h1{{font-size:clamp(20px,3vw,30px);font-weight:600;margin:0 0 6px;letter-spacing:-.02em}}
.sub{{color:var(--dim);font-size:13px;margin:0 0 4px}}
.meta{{font-family:var(--mono);font-size:10.5px;color:#6f6961;letter-spacing:.06em;margin-top:14px}}
h2{{font-size:11px;font-family:var(--mono);letter-spacing:.22em;text-transform:uppercase;
color:var(--acc);margin:46px 0 14px;font-weight:400;border-bottom:1px solid var(--line);padding-bottom:10px}}
table{{width:100%;border-collapse:collapse;font-size:12.5px}}
th{{text-align:left;font-weight:500;font-size:10px;letter-spacing:.14em;text-transform:uppercase;
color:var(--dim);padding:0 10px 8px;border-bottom:1px solid var(--line)}}
td{{padding:9px 10px;border-bottom:1px solid #1e1b18;vertical-align:top}}
.code{{font-family:var(--mono);color:var(--acc);width:44px}}
.lvl{{width:56px;font-size:11px;text-align:right}}
tr.pass .lvl{{color:var(--ok)}}tr.warn .lvl{{color:var(--warn)}}tr.error .lvl{{color:var(--bad)}}
tr.warn{{background:rgba(217,162,74,.05)}}tr.error{{background:rgba(194,96,79,.07)}}
.num{{font-family:var(--mono);text-align:right;width:90px}}
.g-measured{{color:var(--ok)}}.g-inferred{{color:var(--warn)}}.g-standard{{color:var(--dim)}}
.src{{color:#6f6961;font-size:11.5px}}
.note{{margin-top:40px;padding:16px 18px;border-left:2px solid var(--acc);background:#191614;
font-size:12.5px;color:var(--dim);line-height:1.85}}
.note b{{color:var(--ink);font-weight:500}}
</style></head><body>
<h1>{ir["title"]}</h1>
<p class="sub">{ir["subtitle"]}</p>
<p class="meta">IR {ir["ir_version"]} · 指纹 {fp} · 参考等级 {ir["grade"]} · {len(ir["parts"])} 个构件</p>

<h2>一、结构检查</h2>
<table><thead><tr><th>编号</th><th>检查项</th><th>结果</th><th>结论</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>

<h2>二、尺寸来源</h2>
<table><thead><tr><th>构件</th><th>尺寸</th><th>值</th><th>成色</th><th>来源</th></tr></thead>
<tbody>{''.join(detail_rows)}</tbody></table>

<div class="note">
<b>怎么读这份报告。</b>「实测」指图上有明确标注；「标准」指取自公开标准（NEMA / GB / ISO）；
「推断」指按比例、对称性或工程先验得出，<b>未经图纸确认</b>。<br>
推断项不是缺陷，是<b>待确认清单</b>——请把它们当作问题，逐条回答，比看一版"看起来对"的渲染有用得多。
</div>
</body></html>
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="SpecSheet → 确认页 + 一致性报告")
    ap.add_argument("spec", help="SpecSheet 路径（.yaml / .json）")
    ap.add_argument("--out", default="spec/out", help="输出目录")
    ap.add_argument("--vendor", default=None,
                    help="vendor 根目录（默认自动从输出目录推算到 assets/vendor）")
    ap.add_argument("--json", action="store_true", help="只输出 IR，不生成页面")
    args = ap.parse_args()

    spec_path = Path(args.spec).resolve()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    spec = load_spec(spec_path)
    ir = build_ir(spec)
    fp = fingerprint(ir)

    if args.json:
        (out_dir / f"{ir['id']}.ir.json").write_text(
            json.dumps(ir, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(ir, ensure_ascii=False, indent=2))
        return

    if not RUNTIME.is_file():
        die(f"缺少运行时：{RUNTIME}")
    runtime = RUNTIME.read_text(encoding="utf-8")
    css = STYLE.read_text(encoding="utf-8") if STYLE.is_file() else ""

    # vendor 相对路径：默认假设产物在 <repo>/spec/out/，vendor 在 <repo>/assets/vendor/
    if args.vendor:
        vendor_rel = Path(args.vendor).as_posix().rstrip("/") + "/"
    else:
        rel = Path(os_relpath(ROOT / "assets" / "vendor", out_dir))
        vendor_rel = rel.as_posix().rstrip("/") + "/"

    page = render_page(ir, runtime, css, vendor_rel)
    (out_dir / f"{ir['id']}.html").write_text(page, encoding="utf-8")
    (out_dir / f"{ir['id']}.ir.json").write_text(
        json.dumps(ir, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / f"{ir['id']}.report.html").write_text(render_report(ir, fp, css), encoding="utf-8")

    # ── 终端摘要 ──
    rep = ir["report"]
    bad = [c for c in rep["checks"] if c["level"] == "error"]
    warn = [c for c in rep["checks"] if c["level"] == "warn"]
    print()
    print(f"  {ir['title']}  ·  {len(ir['parts'])} 构件  ·  指纹 {fp}")
    print(f"  {'─' * 62}")
    for c in rep["checks"]:
        mark = {"pass": "PASS", "warn": "WARN", "error": "FAIL"}[c["level"]]
        print(f"  [{mark}] {c['code']}  {c['title']}")
        print(f"         {c['detail']}")
    print(f"  {'─' * 62}")
    print(f"  证据覆盖率 {(rep['coverage'] * 100):.0f}%   "
          f"实测 {rep['counts']['measured']} / 推断 {rep['counts']['inferred']} / 标准 {rep['counts']['standard']}")
    print(f"  输出  {out_dir / (ir['id'] + '.html')}")
    print(f"        {out_dir / (ir['id'] + '.report.html')}")
    print()
    sys.exit(1 if bad else 0)


def os_relpath(target: Path, start: Path) -> str:
    import os
    return os.path.relpath(str(target), str(start))


if __name__ == "__main__":
    main()
