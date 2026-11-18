#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
visual-3d-forge / timeline_check.py
把「提示表」当契约检查：一段 E2/E3 体验的时间轴，能不能被机器验一遍。

为什么需要它
------------
时序作品最常见的三种死法，全都静态可查：

1. **多个时钟**。每个物体自己 `performance.now()`，切标签页后互相漂移，
   卡节拍的东西散了，而且没有单一「当前时间」可以打印出来看。
2. **提示表有洞**。第 3 场到第 4 场之间没人负责，画面保持在上一场的最后一帧，
   观众以为卡死了。
3. **缓动默认线性**。真实运动几乎没有线性的；全线性读起来像机械臂。

这个脚本读一个纯数据的提示表（JSON），把这三件事连同越界、重号、
时长不整除一起钉死。它不执行 JS，只看结构。

用法
----
    python3 timeline_check.py timeline.json
    python3 timeline_check.py timeline.json --json
    python3 timeline_check.py timeline.json --strict     # 有 warning 也失败

提示表格式（最小集）
--------------------
    {
      "duration": 122.0,
      "bpm": 174,                       // 可选；有则检查整除
      "master_clock": "audio",          // audio | raf | input
      "cues": [
        {"t": 0.0,  "id": "fade-in", "dur": 1.2, "ease": "outQuad", "apply": "exposure"},
        {"t": 30.313, "id": "scene-switch", "dur": 0.0, "ease": "none", "apply": "badness"}
      ]
    }

退出码：0 通过（可含 warning）；1 有 error 或 strict 下有 warning；2 文件不可读。
只用标准库。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 允许的缓动名。线性不在默认白名单里——不是不能线性，是必须显式写 "linear"
EASES = {
    "linear", "none",
    "inQuad", "outQuad", "inOutQuad",
    "inCubic", "outCubic", "inOutCubic",
    "inQuint", "outQuint", "inOutQuint",
    "inSine", "outSine", "inOutSine",
    "inExpo", "outExpo", "inOutExpo",
    "parabola", "bounce", "elastic", "back",
    "step", "hold",
}

# 参与「谁在计时」的字段名：出现多处就说明可能有多时钟
CLOCK_KEYS = ("master_clock", "clock")


class Report:
    def __init__(self) -> None:
        self.errors: list[tuple[str, str]] = []
        self.warns: list[tuple[str, str]] = []
        self.passes: list[str] = []

    def err(self, code: str, msg: str) -> None:
        self.errors.append((code, msg))

    def warn(self, code: str, msg: str) -> None:
        self.warns.append((code, msg))

    def ok(self, msg: str) -> None:
        self.passes.append(msg)

    def dump(self, as_json: bool) -> int:
        code = 1 if self.errors else 0
        if as_json:
            print(json.dumps({
                "ok": not self.errors,
                "passes": self.passes,
                "warnings": [{"code": c, "message": m} for c, m in self.warns],
                "errors": [{"code": c, "message": m} for c, m in self.errors],
            }, ensure_ascii=False, indent=2))
            return code
        print("\n=== 提示表自检 · timeline_check v1 ===\n")
        for m in self.passes:
            print(f"  [PASS] {m}")
        if self.warns:
            print()
            for c, m in self.warns:
                print(f"  [WARN {c}] {m}")
        if self.errors:
            print()
            for c, m in self.errors:
                print(f"  [FAIL {c}] {m}")
        print()
        print(f"  结果：{len(self.passes)} 通过 / {len(self.warns)} 警告 / {len(self.errors)} 失败")
        return code


def load(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    # 允许注释：提示表是手写的，注释比文档更贴近现场
    text = re.sub(r"^\s*//.*$", "", text, flags=re.M)
    return json.loads(text)


def main() -> int:
    ap = argparse.ArgumentParser(description="提示表（timeline）结构自检")
    ap.add_argument("file", help="timeline.json")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    ap.add_argument("--strict", action="store_true", help="有 warning 也失败")
    args = ap.parse_args()

    path = Path(args.file)
    if not path.is_file():
        print(f"读不到文件：{path}", file=sys.stderr)
        return 2
    try:
        spec = load(path)
    except json.JSONDecodeError as e:
        print(f"[timeline] JSON 解析失败：{e}", file=sys.stderr)
        return 2

    r = Report()
    duration = spec.get("duration")
    cues = spec.get("cues")

    # ── T01 基本形状 ──────────────────────────────────────────────
    if not isinstance(duration, (int, float)) or duration <= 0:
        r.err("T01", "缺少 duration（正数），无法判断提示表覆盖范围")
        duration = 0.0
    else:
        r.ok(f"总时长 {duration:.3f}s")

    if not isinstance(cues, list) or not cues:
        r.err("T01", "缺少 cues 数组，或它是空的")
        cues = []
    else:
        r.ok(f"提示条数 {len(cues)}")

    # ── T02 主时钟声明 ─────────────────────────────────────────────
    clock = spec.get("master_clock") or spec.get("clock")
    if clock is None:
        r.err("T02", "没有声明 master_clock（audio / raf / input）。"
                     "未声明的时钟会退化成「每个物体自己计时」，切标签页后必然漂移")
    elif clock not in ("audio", "raf", "input"):
        r.warn("T02", f"master_clock={clock!r} 不在约定集合内（audio/raf/input）")
    else:
        r.ok(f"主时钟：{clock}")

    # ── T03 每条 cue 的必备字段 ────────────────────────────────────
    ids: dict[str, int] = {}
    missing_id, missing_t, bad_ease, no_apply = [], [], [], []
    for i, c in enumerate(cues):
        if not isinstance(c, dict):
            r.err("T03", f"第 {i} 条 cue 不是对象")
            continue
        cid = c.get("id")
        if not cid:
            missing_id.append(i)
        else:
            ids[cid] = ids.get(cid, 0) + 1
        if "t" not in c or not isinstance(c["t"], (int, float)):
            missing_t.append(cid or i)
        if c.get("dur", 0) and c.get("ease", "none") not in EASES:
            bad_ease.append((cid, c.get("ease")))
        if "apply" not in c:
            no_apply.append(cid or i)

    if missing_id:
        r.err("T03", f"{len(missing_id)} 条 cue 没有 id：{missing_id[:6]}"
                     "（出问题时你要能说「坏在 glitch-1」，而不是「大概第 6 秒」）")
    if missing_t:
        r.err("T03", f"{len(missing_t)} 条 cue 没有 t：{missing_t[:6]}")
    if bad_ease:
        r.err("T04", f"未登记的缓动：{bad_ease[:6]}（允许值见脚本 EASES）")
    elif any(c.get("dur") for c in cues if isinstance(c, dict)):
        r.ok("缓动名全部合法")
    if no_apply:
        r.warn("T05", f"{len(no_apply)} 条 cue 没有 apply 字段：{no_apply[:6]}"
                      "（提示表应只算状态，不该直接改场景）")

    dup = [k for k, v in ids.items() if v > 1]
    if dup:
        r.err("T06", f"id 重号：{dup[:6]}")

    # ── T07 时间范围与单调 ────────────────────────────────────────
    timed = [(c.get("t"), c) for c in cues if isinstance(c, dict) and isinstance(c.get("t"), (int, float))]
    timed.sort(key=lambda x: x[0])
    if duration:
        over = [c.get("id") or c.get("t") for t, c in timed
                if t > duration or t + (c.get("dur") or 0) > duration + 1e-6]
        if over:
            r.err("T07", f"{len(over)} 条 cue 越过总时长 {duration:.3f}s：{over[:6]}")
        else:
            r.ok("没有 cue 越过总时长")
        if timed and timed[0][0] > 0.5:
            r.warn("T08", f"第一条 cue 在 {timed[0][0]:.3f}s，前 {timed[0][0]:.2f}s 无人负责"
                          f"（开场空白会让观众以为还没加载完）")
    if timed:
        r.ok(f"起点 {timed[0][0]:.3f}s　终点 {max(t + (c.get('dur') or 0) for t, c in timed):.3f}s")

    # ── T09 覆盖空洞 ─────────────────────────────────────────────
    # 只检查「声明了 dur」的连续段；dur=0 的是瞬时切换，不参与覆盖
    spans = sorted((c["t"], c["t"] + (c.get("dur") or 0), c.get("id"))
                   for _, c in timed if (c.get("dur") or 0) > 0)
    gaps = []
    for (s1, e1, id1), (s2, e2, id2) in zip(spans, spans[1:]):
        if s2 > e1 + 1e-6:
            gaps.append((round(e1, 3), round(s2, 3), id1, id2))
    if gaps:
        r.warn("T09", f"{len(gaps)} 处覆盖空洞（上一段结束到下一段开始之间无人负责）："
                      f"{gaps[:4]}。如果这是刻意留白，请在 cue 上写明 id 说明")
    elif spans:
        r.ok(f"覆盖连续（{len(spans)} 段有 dur 的 cue 首尾相接或重叠）")

    # ── T10 节拍整除 ─────────────────────────────────────────────
    bpm = spec.get("bpm")
    if isinstance(bpm, (int, float)) and bpm > 0 and duration:
        beat = 60.0 / bpm
        beats = duration / beat
        nearest = round(beats)
        drift = abs(beats - nearest)
        if drift > 0.02:
            r.warn("T10", f"{duration:.3f}s ÷ (60/{bpm}) = {beats:.3f} 拍，"
                          f"不是整数拍（差 {drift:.3f}）。片尾会卡在半拍上")
        else:
            r.ok(f"{duration:.3f}s = {nearest} 拍 @ {bpm} BPM（整除）")

        # cue 是否落在节拍网格上
        offbeat = []
        for t, c in timed:
            pos = t / beat
            if abs(pos - round(pos)) > 0.02:
                offbeat.append((c.get("id"), round(t, 3), round(pos, 2)))
        if offbeat:
            r.warn("T11", f"{len(offbeat)} 条 cue 不在节拍网格上：{offbeat[:5]}"
                          f"（若是刻意的错拍，请在 id 里写明 off-beat）")
        elif timed:
            r.ok(f"全部 {len(timed)} 条 cue 落在 {bpm} BPM 的节拍网格上")

    # ── T12 降级档声明 ───────────────────────────────────────────
    tiers = spec.get("quality_tiers")
    if tiers is None:
        r.warn("T12", "没有声明 quality_tiers。E2/E3 必须能在弱机上降级，"
                      "而且降的是算法复杂度（tessellation / blur / steps），不是只有像素比")
    elif not isinstance(tiers, dict) or len(tiers) < 2:
        r.warn("T12", f"quality_tiers 只有 {len(tiers) if isinstance(tiers, dict) else 0} 档，至少两档")
    else:
        r.ok(f"降级档：{'/'.join(tiers)}")
        # 检查每档是否真的有结构差异
        keys = set()
        for name, cfg in tiers.items():
            if isinstance(cfg, dict):
                keys |= set(cfg)
        structural = keys & {"tessellation", "blur", "blurSteps", "chromaticSteps",
                             "reflectionSize", "textureSize", "particles", "shadowMap"}
        if not structural:
            r.warn("T13", f"降级档只改了 {sorted(keys)[:6]}，没有算法复杂度字段"
                          f"（tessellation/blur/chromaticSteps/textureSize）。"
                          f"只降像素比等于没降级")
        else:
            r.ok(f"降级涉及结构字段：{sorted(structural)}")

    # ── T14 减少动态 ─────────────────────────────────────────────
    if not spec.get("reduced_motion"):
        r.warn("T14", "没有声明 reduced_motion 降级路径。"
                      "prefers-reduced-motion 时应有明确行为（跳过转场 / 关持续动画）")
    else:
        r.ok(f"reduced-motion 降级：{spec['reduced_motion']}")

    code = r.dump(args.json)
    if args.strict and r.warns and not r.errors:
        return 1
    return code


if __name__ == "__main__":
    sys.exit(main())
