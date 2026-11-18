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

def _local_xy_to_world(p: dict, at: list[float]) -> list[float]:
    """把拉伸体的局部平面坐标换成世界偏移。

    必须和运行时 alignExtrude 对齐，否则尺寸标注会落在零件外面 ——
    ExtrudeGeometry 默认沿 +Z 拉伸，axis=x 时整体绕 Y 转 90°，形状的 x 轴因此变成 −z。
    """
    ax = p.get("axis", "x")
    if ax == "x":
        return [0.0, at[1], -at[0]]
    if ax == "y":
        return [at[0], 0.0, -at[1]]
    return [at[0], at[1], 0.0]


PARAM_HINTS = ("齿数", "模数", "减速比", "级数", "个数", "数量", "角度", "重量", "材质")


def is_param(key: str, ev: dict) -> bool:
    """无量纲量不参与几何定位。

    齿数、模数、减速比是生成几何的**输入**，不是能从几何上量出来的**结果**。
    把它们算进分母，会让定位率永远虚低，也会掩盖真正量错的尺寸。
    """
    if ev.get("param") is True:
        return True
    return any(h in key for h in PARAM_HINTS)


def locate_evidence(parts: list[dict], pos: dict, tol_abs: float = 0.8,
                    tol_rel: float = 0.02) -> dict:
    """把每条尺寸钉回几何上。

    人只写「机身长 56」，编译器去量这个零件的包围盒：X 跨 56.00 → 钉上。
    这不是显示技巧。**一个数字如果在几何上找不到落点，它就没有被验证过** ——
    它可能量的是别的零件，也可能是笔误。P1 的全部意义就是让这句话可执行。

    五种落点，按误差最小者胜：
      span      沿某轴的跨度（长、宽、厚、法兰边长）
      diameter  回转体的径向直径（车身直径、内径）
      profile   回转轮廓某一段的直径（扁位、台阶）
      hole      单个孔的直径
      pitch     孔心距 / 孔分布圆直径
    容差取 max(0.8 mm, 2%)：更小的偏差在确认件阶段没有意义，
    但放宽到 5% 时「分布圆」会误配到别的跨度上，反而骗人。
    """
    def tol(v: float) -> float:
        return max(tol_abs, abs(v) * tol_rel)

    located = total = 0
    orphans: list[str] = []
    params: list[str] = []

    for p in parts:
        uid = p["uid"]
        evs = p.get("evidence") or {}
        if not evs:
            continue
        lo, hi = part_aabb(p, pos[uid])
        span = {"x": hi[0] - lo[0], "y": hi[1] - lo[1], "z": hi[2] - lo[2]}
        c = [(lo[i] + hi[i]) / 2.0 for i in range(3)]
        rax = {"x": ("y", "z"), "y": ("x", "z"), "z": ("x", "y")}[p.get("axis", "x")]
        prm = p.get("params") or {}

        # 孔心（世界坐标）与孔心距，先算一遍
        hole_pts: list[list[float]] = []
        hole_ds: list[float] = []
        # holes 在 IR 里已展开成多边形：中心和直径从包围盒反推，
        # 圆形与任意形状都适用，不用再回看 DSL。
        for h in (prm.get("holes") or []):
            if not h:
                continue
            xs = [q[0] for q in h]
            ys = [q[1] for q in h]
            d = max(max(xs) - min(xs), max(ys) - min(ys))
            if d <= 1e-6:
                continue
            off = _local_xy_to_world(p, [(max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2])
            hole_pts.append([pos[uid][i] + off[i] for i in range(3)])
            hole_ds.append(float(d))

        for key, ev in evs.items():
            if is_param(key, ev):
                params.append(f"{uid}·{key}")
                continue
            total += 1
            v = float(ev["value"])
            cands: list[tuple[float, str, list[float], list[float], str]] = []

            def add(err, kind, a, b):
                if err <= tol(v):
                    cands.append((err, kind, a, b, kind))

            # ① bbox 跨度
            for ax in "xyz":
                i = "xyz".index(ax)
                a = list(c); a[i] = lo[i]
                b = list(c); b[i] = hi[i]
                add(abs(span[ax] - v), "span", a, b)

            # ② 回转体径向直径
            if p["kind"] in ("revolve", "gear"):
                i = "xyz".index(rax[1])
                dia = max(span[rax[0]], span[rax[1]])
                a = list(c); a[i] = c[i] - dia / 2
                b = list(c); b[i] = c[i] + dia / 2
                add(abs(dia - v), "diameter", a, b)

                # ③ 轮廓某一段的直径（扁位、台阶、内腔）
                ai = "xyz".index(p.get("axis", "x"))
                # 轮廓某一段的直径：落点是该段中点处的一条径向线，
                # 不是轴向跨度 —— 扁位、台阶这类特征只沿径向可量。
                for (r1, a1), (r2, a2) in zip(prm["profile"], prm["profile"][1:]):
                    if abs(r1 - r2) > 1e-6 or r1 <= 1e-3:
                        continue
                    rj = "xyz".index(rax[1])
                    mid = pos[uid][ai] + (min(a1, a2) + max(a1, a2)) / 2.0
                    a = list(c); b = list(c)
                    a[ai] = mid; b[ai] = mid
                    a[rj] = c[rj] - r1
                    b[rj] = c[rj] + r1
                    add(abs(2 * r1 - v), "profile", a, b)

            # ④ 单个孔
            if hole_ds:
                k = min(range(len(hole_ds)), key=lambda j: abs(hole_ds[j] - v))
                d = abs(hole_ds[k] - v)
                if d <= tol(v):
                    # 孔的直径要横着量：孔轴是拉伸方向，沿轴量到的是壁厚。
                    rj = "xyz".index(rax[1])
                    r = v / 2
                    a = list(hole_pts[k]); a[rj] -= r
                    b = list(hole_pts[k]); b[rj] += r
                    cands.append((d, "hole", a, b, "hole"))

                # ⑤ 孔心距 / 分布圆
                for i in range(len(hole_pts)):
                    for j in range(i + 1, len(hole_pts)):
                        dd = sum((hole_pts[i][t] - hole_pts[j][t]) ** 2 for t in range(3)) ** 0.5
                        if dd >= v - tol(v):
                            a, b = list(hole_pts[i]), list(hole_pts[j])
                            cands.append((abs(dd - v), "pitch", a, b, "pitch"))

            if not cands:
                orphans.append(f"{uid}·{key}")
                continue

            err, kind, a, b, _ = min(cands, key=lambda t: t[0])
            ev["anchor"] = {
                "uid": uid, "kind": kind, "axis": p.get("axis", "x"),
                "err": round(err, 3),
                "a": [round(x, 3) for x in a],
                "b": [round(x, 3) for x in b],
            }
            located += 1

    return {"located": located, "total": total, "orphans": orphans, "params": params}


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

    # C6 证据定位率：每个数字必须能在几何上找到落点
    loc = locate_evidence(parts, pos)
    loc_rate = loc["located"] / (loc["total"] or 1)
    checks.append({
        "code": "C6", "level": "pass" if loc_rate >= 0.7 else "warn",
        "title": "证据定位率",
        "detail": (
            f"{loc['located']}/{loc['total']} 项尺寸已在几何上定位（容差 0.8 mm / 2%）；"
            f"另 {len(loc['params'])} 项为无量纲参数，不参与定位"
            + ("；未定位：" + "、".join(loc["orphans"][:5]) + ("…" if len(loc["orphans"]) > 5 else "")
               if loc["orphans"] else "；全部尺寸可定位")
        ),
    })

    return {"checks": checks, "coverage": round(coverage, 4), "counts": counts,
            "total": total, "located": loc["located"], "ev_total": loc["total"],
            "orphans": loc["orphans"], "params": loc["params"]}



# ────────────────────────────── 输出 ──────────────────────────────

def build_ir(spec: dict) -> dict:
    # 深拷贝：anchor 要写回 evidence，不能污染调用方传进来的 spec
    parts = [expand_part(json.loads(json.dumps(p, ensure_ascii=False))) for p in spec["parts"]]
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
