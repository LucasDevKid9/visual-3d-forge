#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
experience_plan.py — 需求 → 体验蓝图（Experience Blueprint）

把一句话需求编译成一份可直接执行的体验蓝图：
六段式填表 / 幕表 / 张力曲线 / 时间栅格 / 声音清单 / 自检项。

纯标准库，无外部依赖。

用法：
    python3 experience_plan.py --brief "给行星齿轮减速器做一个产品发布体验" \
        --preset product --bpm 140 --duration 60 -o blueprint.md

    python3 experience_plan.py --preset brand --scenes 10 --bpm 174 --duration 50
    python3 experience_plan.py --list-presets
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

# ----------------------------------------------------------------------------
# 预设：曲线 / 动词池 / 段落配比
# ----------------------------------------------------------------------------

PRESETS = {
    "product": {
        "label": "产品发布",
        "curve": "single_peak",
        "scenes": 6,
        "duration": 60,
        "bpm": 140,
        "verbs": ["look", "turn", "open", "combine", "break", "read"],
        "tone": "克制、精密、可信任",
        "climax_at": 0.72,
    },
    "brand": {
        "label": "品牌体验",
        "curve": "double_peak",
        "scenes": 10,
        "duration": 50,
        "bpm": 174,
        "verbs": ["tap", "look", "knock", "enter", "walk", "read",
                  "hold", "knock", "choose", "break"],
        "tone": "强烈、有性格、可传播",
        "climax_at": 0.85,
    },
    "data": {
        "label": "数据叙事",
        "curve": "staircase",
        "scenes": 7,
        "duration": 90,
        "bpm": 110,
        "verbs": ["read", "look", "turn", "choose", "combine", "read", "read"],
        "tone": "清晰、有据、层层递进",
        "climax_at": 0.78,
    },
    "portfolio": {
        "label": "可玩作品集",
        "curve": "loop",
        "scenes": 8,
        "duration": 180,
        "bpm": 128,
        "verbs": ["enter", "choose", "drag", "hold", "knock", "combine",
                  "break", "read"],
        "tone": "自信、有游戏感、鼓励探索",
        "climax_at": 0.8,
    },
    "ambient": {
        "label": "氛围 / 纪念",
        "curve": "decay",
        "scenes": 5,
        "duration": 75,
        "bpm": 90,
        "verbs": ["look", "walk", "look", "hold", "read"],
        "tone": "安静、留白、有余味",
        "climax_at": 0.3,
    },
}

CURVES = {
    "single_peak": [3, 5, 7, 9, 6, 4],
    "double_peak": [3, 5, 4, 7, 5, 8, 6, 9, 7, 5],
    "staircase": [2, 4, 5, 6, 7, 8, 6],
    "decay": [9, 7, 5, 3, 2],
    "loop": [5, 7, 4, 8, 6, 9, 5, 6],
}

VERB_META = {
    "look":    ("看", "鼠标移动 / 陀螺仪", "视差 + 景深，延迟 ≤ 1 帧"),
    "turn":    ("转", "拖拽", "惯性阻尼，松手余速 0.3s"),
    "tap":     ("点", "click / tap", "命中判定放大 20%"),
    "drag":    ("拖", "pointerdown + move", "拖动体粘在指针上"),
    "hold":    ("按", "持续按住", "蓄力条 + 阈值 + 预热反馈"),
    "knock":   ("敲", "快速连击", "每次敲击独立音效"),
    "swipe":   ("划", "手势方向", "方向判定用位移而非末速"),
    "shake":   ("摇", "设备加速度", "阈值 + 冷却 ≥ 600ms"),
    "choose":  ("选", "多选 + 确认", "预览即时，不等确认"),
    "combine": ("组", "多选 + 拼合", "吸附半径 = 目标尺寸 × 0.15"),
    "enter":   ("入", "点击 / 走近", "转场用 Iris 或 Push"),
    "walk":    ("走", "WASD / 拖拽前进", "相机 lerp 0.08"),
    "open":    ("开", "拖拽 / 点击", "剖切面 + 内部高亮"),
    "break":   ("破", "连击 / 蓄力后释放", "碎块物理 + 冲击音"),
    "read":    ("读", "静止", "唯一允许无交互的幕"),
}

SEGMENTS = [
    ("GATE",       "门槛", 0.04, "建立预期 + 拿到授权（档位 / 声音 / 分级）"),
    ("ONBOARDING", "引导", 0.07, "教会唯一必需的动作"),
    ("JOURNEY",    "旅程", 0.66, "主体，分段推进"),
    ("CLIMAX",     "高潮", 0.10, "情绪峰值，全片最贵的一秒"),
    ("RESOLUTION", "收束", 0.09, "把体验收进一句话"),
    ("REMNANT",    "痕迹", 0.04, "带走的东西"),
]

SOUND_PLAN = [
    ("节拍器", "Metronome", "低频 click，仅在小节首拍", "0.05"),
    ("状态音", "State", "click / confirm / impact", "0.20–0.45"),
    ("材质音", "Material", "按主体材质选配方（金属/玻璃/木/布/水）", "0.15–0.30"),
    ("氛围音", "Ambience", "55Hz 微失谐正弦 + 低通", "0.09"),
]


# ----------------------------------------------------------------------------
# 计算
# ----------------------------------------------------------------------------

def grid(bpm: float) -> dict:
    beat = 60.0 / bpm
    return {
        "bpm": bpm,
        "beat": beat,
        "bar": beat * 4,
        "phrase": beat * 16,
    }


def snap(seconds: float, unit: float, sub: int = 2) -> float:
    step = unit / sub
    return round(round(seconds / step) * step, 4)


def build_curve(name: str, n: int) -> list:
    base = CURVES.get(name, CURVES["single_peak"])
    if n <= len(base):
        # 均匀抽样，保留首尾
        idx = [round(i * (len(base) - 1) / max(1, n - 1)) for i in range(n)]
        return [base[i] for i in idx]
    # 需要更多幕：在峰之间插值
    out = []
    for i in range(n):
        t = i / (n - 1) * (len(base) - 1)
        lo = int(math.floor(t))
        hi = min(lo + 1, len(base) - 1)
        f = t - lo
        out.append(round(base[lo] * (1 - f) + base[hi] * f))
    return out


def verb_sequence(pool: list, n: int) -> list:
    """动词不重复地铺满 n 幕；不够就循环但保证相邻不同。"""
    seq = []
    while len(seq) < n:
        for v in pool:
            if len(seq) >= n:
                break
            if seq and seq[-1] == v:
                continue
            seq.append(v)
    return seq


# ----------------------------------------------------------------------------
# 生成
# ----------------------------------------------------------------------------

def render_ascii_curve(tension: list, width: int = 52) -> str:
    hi = max(tension) or 1
    rows = 6
    grid_rows = [[" "] * width for _ in range(rows)]
    step = max(1, width // max(1, len(tension) - 1))
    for i, v in enumerate(tension):
        x = min(width - 1, i * step)
        y = rows - 1 - round(v / hi * (rows - 1))
        grid_rows[y][x] = "●"
    lines = ["```"]
    for r, row in enumerate(grid_rows):
        lines.append(f"{hi - r:>2} │" + "".join(row))
    lines.append("   └" + "─" * width)
    lines.append("    " + "".join(str((i + 1) % 10) for i in range(0, len(tension))) + "  幕")
    lines.append("```")
    return "\n".join(lines)


def build_plan(brief: str, preset_key: str, scenes: int, duration: float, bpm: float) -> str:
    p = PRESETS[preset_key]
    g = grid(bpm)
    tension = build_curve(p["curve"], scenes)
    verbs = verb_sequence(p["verbs"], scenes)

    # 幕时长：总时长按张力加权分配，再吸附到小节
    weights = [max(1, t) for t in tension]
    raw = [duration * w / sum(weights) for w in weights]
    durs = [max(g["bar"], snap(r, g["bar"])) for r in raw]

    # 段配比
    seg_lines = []
    acc = 0.0
    for key, cn, ratio, desc in SEGMENTS:
        sec = round(duration * ratio, 2)
        seg_lines.append(
            f"| **{key}** {cn} | {ratio*100:.0f}% | {sec:.1f}s | {desc} |"
        )
        acc += sec

    scene_rows = []
    for i, (v, t, d) in enumerate(zip(verbs, tension, durs), 1):
        cn, how, key = VERB_META.get(v, (v, "—", "—"))
        bars = d / g["bar"]
        scene_rows.append(
            f"| {i:02d} | `{v}` {cn} | {how} | {key} | {t}/10 | {d:.2f}s | {bars:.1f} |"
        )

    sound_rows = [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in SOUND_PLAN]

    verb_dupes = []
    for i in range(1, len(verbs)):
        if verbs[i] == verbs[i - 1]:
            verb_dupes.append(i + 1)

    tension_jumps = [abs(tension[i] - tension[i - 1]) for i in range(1, len(tension))]
    flat_runs = 0
    run = 1
    for j in tension_jumps:
        if j < 2:
            run += 1
            flat_runs = max(flat_runs, run)
        else:
            run = 1

    total_bars = sum(durs) / g["bar"]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    md = f"""# 体验蓝图 · Experience Blueprint

> 生成于 {now}　|　预设：**{p['label']}**（`{preset_key}`）
> 需求：{brief or "（未填写）"}

---

## 一、六段式填表

| 段 | 占比 | 时长 | 作用 |
|---|---|---|---|
{chr(10).join(seg_lines)}
| **合计** | 100% | {acc:.1f}s | — |

**填不满三段以上就不要开始写代码。**

---

## 二、时间栅格

| 参数 | 值 |
|---|---|
| BPM | **{bpm:.0f}** |
| 1 拍 beat | {g['beat']:.4f} s |
| 1 小节 bar | {g['bar']:.4f} s |
| 1 乐句 phrase | {g['phrase']:.4f} s |
| 全片总长 | {duration:.1f} s ≈ **{total_bars:.1f} 小节** |

**所有转场 / 镜头位移 / 材质过渡的 duration 都必须吸附到 1/2 拍栅格**，误差 ≤ 1/4 拍。

```js
const beat = 60 / {bpm:.0f};              // {g['beat']:.4f}s
const snap = (s, sub = 2) => Math.round(s / (beat / sub)) * (beat / sub);
```

---

## 三、幕表

| # | 动词 | 输入方式 | 手感关键 | 张力 | 时长 | 小节 |
|---|---|---|---|---|---|---|
{chr(10).join(scene_rows)}

**动词不重复检查**：{"✅ 通过" if not verb_dupes else "❌ 第 " + "、".join(map(str, verb_dupes)) + " 幕与前幕重复"}

---

## 四、张力曲线

{render_ascii_curve(tension)}

- 相邻差 < 2 的连续段最长：**{flat_runs}** 幕（≤ 2 为佳）
- 峰值位置：第 **{tension.index(max(tension)) + 1}** 幕（建议落在全片 {p['climax_at']*100:.0f}% 处）
- 收尾张力：**{tension[-1]}/10**（不应为 0，也不应为 10）

**曲线型**：`{p['curve']}` — {p['tone']}

---

## 五、声音清单

| 角色 | 类型 | 配方 | 音量 |
|---|---|---|---|
{chr(10).join(sound_rows)}

**硬约束**：
- 进入页面**不自动出声**，显示 `SOUND ON/OFF`
- 全站音效 ≤ 8 种
- 全静音状态下必须能走完六段式
- 不用 `setInterval` 打拍子，用音频时钟反推

---

## 六、引导与反馈

| 幕 | 引导层级 | 文案（≤8 字） | 反馈三通道 |
|---|---|---|---|
"""
    for i, v in enumerate(verbs, 1):
        cn, how, key = VERB_META.get(v, (v, "—", "—"))
        level = "不教" if v in ("look", "turn", "tap") else "轻教" if v in ("drag", "choose", "enter", "walk") else "重教"
        text = {"look": "看看它", "turn": "拖拽转动", "hold": "按住蓄力",
                "knock": "敲击", "break": "击碎它", "read": "—"}.get(v, f"{cn}一下")
        md += f"| {i:02d} | {level} | {text} | 视觉 + 听觉{' + 触觉' if level == '重教' else ''} |\n"

    md += f"""
---

## 七、状态机

```
GATE → ONBOARDING → SCENE_01 … SCENE_{scenes:02d} → OUTRO → END
         ↑              ↓                    ↓
         └──── 重玩 ────┴──── SKIP ──────────┘
```

**必备四条边**：
1. `LOADING → READY` 守卫：资源就绪 + 用户已交互
2. `任意 → PAUSED`（`visibilitychange`）
3. `任意 → SKIP → OUTRO`（单幕 > 8s 或总长 > 90s 时必须给）
4. `OUTRO → GATE` 重玩

**实现要点**：状态变更只走 `go()`，禁止在事件回调里直接改 `state`。

---

## 八、自检清单

- [ ] 六段式至少填满 4 段
- [ ] 动词种类 ≤ 5，相邻幕不同
- [ ] 3 秒内能完成第一次成功交互
- [ ] 每幕只有一个视觉主体 + 一个交互目标
- [ ] 相邻张力差 ≥ 2，无三幕同值
- [ ] 峰值幕 ≤ 2 个
- [ ] 所有 duration 吸附到 1/2 拍栅格
- [ ] 声音默认关闭，有可见开关
- [ ] 全静音能走完六段式
- [ ] `prefers-reduced-motion` 下时间 ×0.25，仍能走完
- [ ] 移动端：触控目标 ≥ 44px，无 hover 依赖
- [ ] 阻尼用帧率无关写法 `1 - Math.pow(k, dt)`
- [ ] 无死路：任何状态可退出且不丢进度
- [ ] 结算页有「数字 + 称号 + 下一步动作」

---

## 九、下一步

1. 把本蓝图交给 `assets/scaffold/experience-shell.html`，按幕表替换 `Machine.register()` 的五个方法
2. 每幕只建它需要的几何（见 `03-geometry-modeling.md`）
3. 跑 `python3 scripts/validate_scene.py <文件> --strict`
4. 跑 `python3 scripts/validate_experience.py <文件>` 做体验完整性检查
"""
    return md


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="把需求编译成体验蓝图（六段式 + 幕表 + 张力曲线 + 时间栅格）"
    )
    ap.add_argument("--brief", default="", help="一句话需求")
    ap.add_argument("--preset", default="product", choices=list(PRESETS),
                    help="预设类型（默认 product）")
    ap.add_argument("--scenes", type=int, default=0, help="幕数（0 = 用预设值）")
    ap.add_argument("--duration", type=float, default=0, help="总时长秒（0 = 用预设值）")
    ap.add_argument("--bpm", type=float, default=0, help="BPM（0 = 用预设值）")
    ap.add_argument("-o", "--out", default="", help="输出 Markdown 路径")
    ap.add_argument("--json", action="store_true", help="额外输出结构化 JSON")
    ap.add_argument("--list-presets", action="store_true", help="列出所有预设")
    args = ap.parse_args(argv)

    if args.list_presets:
        for k, v in PRESETS.items():
            print(f"{k:12s} {v['label']:8s}  幕数 {v['scenes']:2d}  "
                  f"{v['duration']:3.0f}s  {v['bpm']:.0f}BPM  曲线 {v['curve']}")
        return 0

    p = PRESETS[args.preset]
    scenes = args.scenes or p["scenes"]
    duration = args.duration or p["duration"]
    bpm = args.bpm or p["bpm"]

    if scenes < 3:
        print("错误：幕数至少 3（六段式压缩后的下限）", file=sys.stderr)
        return 2
    if scenes > 16:
        print("提示：幕数 > 12 建议拆章节，仍继续生成", file=sys.stderr)

    md = build_plan(args.brief, args.preset, scenes, duration, bpm)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"已写入 {args.out}  ({len(md)} 字符, {scenes} 幕, {bpm:.0f}BPM, {duration:.0f}s)")
    else:
        print(md)

    if args.json:
        g = grid(bpm)
        payload = {
            "brief": args.brief,
            "preset": args.preset,
            "bpm": bpm,
            "grid": g,
            "duration": duration,
            "scenes": [
                {"index": i + 1, "verb": v, "tension": t}
                for i, (v, t) in enumerate(zip(
                    verb_sequence(p["verbs"], scenes),
                    build_curve(p["curve"], scenes)))
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        sys.exit(0)
