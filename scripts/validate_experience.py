#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_experience.py — 体验完整性静态自检

检查一个 HTML 是否具备"可体验"的骨架：状态机 / 幕结构 / 引导 / 声音 / 反馈 /
进度 / 跳过 / 无障碍 / 触控适配。

与 validate_scene.py 互补：
    validate_scene.py       管"三维场景是否站得住"（几何/材质/光照/性能）
    validate_experience.py  管"体验是否成立"（叙事/节奏/交互/反馈）

用法：
    python3 validate_experience.py scene.html
    python3 validate_experience.py scene.html --strict --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 结果容器
# ---------------------------------------------------------------------------

class Report:
    def __init__(self):
        self.rows = []   # (level, code, msg, hint)

    def add(self, level, code, msg, hint=""):
        self.rows.append({"level": level, "code": code, "msg": msg, "hint": hint})

    def err(self, code, msg, hint=""):  self.add("ERROR", code, msg, hint)
    def warn(self, code, msg, hint=""): self.add("WARN", code, msg, hint)
    def ok(self, code, msg):           self.add("OK", code, msg)

    @property
    def errors(self):   return [r for r in self.rows if r["level"] == "ERROR"]
    @property
    def warnings(self): return [r for r in self.rows if r["level"] == "WARN"]

    def render(self):
        icon = {"ERROR": "✗", "WARN": "!", "OK": "✓"}
        lines = []
        for r in self.rows:
            lines.append(f"{icon[r['level']]} [{r['code']}] {r['msg']}")
            if r["hint"] and r["level"] != "OK":
                lines.append(f"      → {r['hint']}")
        lines.append("")
        lines.append(
            f"通过 {len([r for r in self.rows if r['level']=='OK'])} · "
            f"警告 {len(self.warnings)} · 失败 {len(self.errors)}"
        )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------

def strip_comments(html: str) -> str:
    html = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    html = re.sub(r"/\*.*?\*/", "", html, flags=re.S)
    html = re.sub(r"(?m)^\s*//.*$", "", html)
    return html


def count(pattern: str, text: str, flags=0) -> int:
    return len(re.findall(pattern, text, flags))


# ---------------------------------------------------------------------------
# 检查项
# ---------------------------------------------------------------------------

def check(src: str, rep: Report):
    low = src.lower()

    # ---------- 1. 状态机 ----------
    has_machine = bool(
        re.search(r"\b(state|status)\s*[:=]\s*['\"]", src)
        or re.search(r"class\s+\w*Machine", src)
        or re.search(r"\bfsm\b", low)
    )
    has_transition = bool(
        re.search(r"\bgo\s*\(|\bnextScene\s*\(|\btransition\s*\(|\bsetState\s*\(", src)
    )
    if has_machine and has_transition:
        rep.ok("X01", "存在状态机与状态转移入口")
    elif has_machine:
        rep.warn("X01", "有 state 变量但没有统一的转移入口",
                 "所有状态变更应走 go()/setState()，否则会出现两个幕同时活着")
    else:
        rep.err("X01", "未发现状态机",
                "体验的骨架是有限状态机。用 Machine.register() + go() 建立，见 14-experience-architecture.md")

    # ---------- 2. 幕结构 ----------
    scenes = count(r"\.register\s*\(|\bscenes?\s*\.\s*push\s*\(", src)
    if scenes >= 3:
        rep.ok("X02", f"幕结构存在（{scenes} 幕）")
    elif scenes == 0:
        rep.err("X02", "未发现幕结构",
                "至少 3 幕（六段式压缩后的下限），每幕一个动词")
    else:
        rep.warn("X02", f"幕数偏少（{scenes} 幕）",
                 "少于 3 幕难以形成推进感；若确实只有 2 幕，考虑合并成一次连续动作")

    # ---------- 3. 相邻动词重复 ----------
    verbs = re.findall(r"verb\s*:\s*['\"]([\w-]+)['\"]", src)
    dup = [i + 2 for i in range(len(verbs) - 1) if verbs[i] == verbs[i + 1]]
    if dup:
        rep.warn("X03", f"相邻幕动词重复：第 {'、'.join(map(str, dup))} 幕",
                 "同一动词连续出现两幕 = 节奏塌陷。换一个动词，或合并成一幕")
    elif verbs:
        rep.ok("X03", f"动词序列无相邻重复（{len(verbs)} 个）")

    # ---------- 4. 引导 ----------
    has_hint = bool(re.search(r"hint|onboard|tutorial|tip", low))
    if has_hint:
        rep.ok("X04", "存在引导层")
    else:
        rep.warn("X04", "未发现引导层",
                 "非通用动作必须给文字引导；通用动作给视觉 affordance（呼吸/光标）")

    # ---------- 5. 声音默认关闭 + 手势解锁 ----------
    has_audio = bool(re.search(r"AudioContext|webkitAudioContext", src))
    if has_audio:
        gesture_unlock = bool(
            re.search(r"pointerdown|click|touchstart", src)
            and re.search(r"\.resume\s*\(|unlock\s*\(", src)
        )
        if gesture_unlock:
            rep.ok("X05", "音频在用户手势内解锁")
        else:
            rep.err("X05", "AudioContext 未在用户手势内 resume",
                    "浏览器自动播放策略要求：AudioContext 必须在 pointerdown/click 内创建或 resume")

        starts_muted = bool(
            re.search(r"muted\s*=\s*true", src)
            or re.search(r"gain\.value\s*=\s*0\b", src)
        )
        if starts_muted:
            rep.ok("X06", "声音默认静音")
        else:
            rep.warn("X06", "未确认声音默认静音",
                     "进入页面不自动出声；给 SOUND ON/OFF 控件")

        has_toggle = bool(re.search(r"Sound\s*(On|Off)|sound.*aria-pressed|mute", src, re.I))
        if has_toggle:
            rep.ok("X07", "存在声音开关")
        else:
            rep.warn("X07", "未发现声音开关控件")

        # 总线分层
        gains = count(r"createGain\s*\(", src)
        if gains >= 3:
            rep.ok("X08", f"音频总线分层（{gains} 个 Gain 节点）")
        elif gains >= 1:
            rep.warn("X08", "音频总线未分层",
                     "建议 master / sfx / amb 三路，静音只动 master")
    else:
        rep.warn("X06", "未使用 Web Audio",
                 "单文件 HTML 不能带音频文件；用 Web Audio 程序化合成，见 16-sound-and-feedback.md")

    # ---------- 6. 后台暂停 ----------
    if re.search(r"visibilitychange|document\.hidden", src):
        rep.ok("X09", "切后台时暂停渲染")
    else:
        rep.err("X09", "缺 visibilitychange 处理",
                "后台不停渲染 = 烧电 + 回来时间错乱")

    # ---------- 7. reduced-motion ----------
    if re.search(r"prefers-reduced-motion", src):
        rep.ok("X10", "处理了 prefers-reduced-motion")
    else:
        rep.err("X10", "缺 prefers-reduced-motion",
                "开启时时间 ×0.25（不是 0），且六段式仍能走完")

    # ---------- 8. 收束 / 结算 ----------
    has_outro = bool(
        re.search(r"\boutro\b|\bending\b|\bresult\b|\bscore\b|THE END|结算", src, re.I)
    )
    if has_outro:
        rep.ok("X11", "存在收束 / 结算")
    else:
        rep.warn("X11", "未发现收束段",
                 "RESOLUTION 不能急刹；REMNANT 要有可带走的东西（分数/称号/生成物）")

    # ---------- 9. 进度可见 ----------
    has_progress = bool(
        re.search(r"progress|rail|dots?|chapter|step|进度", low)
    )
    if has_progress:
        rep.ok("X12", "存在进度指示")
    else:
        rep.warn("X12", "未发现进度指示",
                 "用户必须随时知道我在哪、还有多久")

    # ---------- 10. 跳过 ----------
    has_skip = bool(re.search(r"\bskip\b", low))
    if has_skip:
        rep.ok("X13", "存在跳过机制")
    else:
        rep.warn("X13", "未发现跳过机制",
                 "单幕 > 8s 或总长 > 90s 时必须给跳过。跳过要加速不要硬切")

    # ---------- 11. 触控适配 ----------
    if re.search(r"@media\s*\(\s*hover\s*:\s*hover", src):
        rep.ok("X14", "悬停效果限定在精确指针设备")
    elif re.search(r":hover", src):
        rep.warn("X14", "hover 效果未做设备限定",
                 "触屏没有 hover；用 @media (hover:hover) and (pointer:fine) 包裹")

    if re.search(r"safe-area-inset", src):
        rep.ok("X15", "适配了安全区")
    else:
        rep.warn("X15", "未适配 safe-area-inset",
                 "刘海屏 / 底部手势条会挡住 HUD")

    if re.search(r"touch-action", src):
        rep.ok("X16", "处理了 touch-action")
    else:
        rep.warn("X16", "未设置 touch-action",
                 "建议 touch-action: manipulation 防双击缩放")

    # ---------- 12. 触觉反馈 ----------
    if re.search(r"navigator\.vibrate", src):
        rep.ok("X17", "移动端有触觉反馈")
    else:
        rep.warn("X17", "无触觉反馈",
                 "移动端成功/失败给 vibrate(≤80ms)，成本极低")

    # ---------- 13. 缓动命名系统 ----------
    eases = set(re.findall(r"--ease-([\w-]+)\s*:", src))
    if len(eases) >= 3:
        rep.ok("X18", f"命名缓动系统（{len(eases)} 条）")
    elif eases:
        rep.warn("X18", f"缓动变量偏少（{len(eases)} 条）",
                 "建议 5–6 条基础曲线：out / in / inout / snap / overshoot")
    else:
        rep.warn("X18", "无命名缓动变量",
                 "命名缓动 = 全站动效同源 = 观感统一。见 15-rhythm-and-timeline.md")

    # ---------- 14. 节奏栅格 ----------
    bpm = re.search(r"BPM\s*=\s*([\d.]+)", src)
    if bpm:
        b = float(bpm.group(1))
        if 60 <= b <= 240:
            rep.ok("X19", f"声明了 BPM = {b:.0f}（beat {60/b:.3f}s）")
        else:
            rep.warn("X19", f"BPM 取值异常：{b}")
        if re.search(r"60\s*/\s*BPM|beat\s*=", src):
            rep.ok("X20", "由 BPM 推导时间栅格")
        else:
            rep.warn("X20", "声明了 BPM 但未用于推导时长",
                     "所有 duration 应吸附到 beat/2 的整数倍")
    else:
        rep.warn("X19", "未声明 BPM",
                 "即使没有声音，也应有时间栅格（beat/bar）统一动效时长")

    # ---------- 15. 帧率无关阻尼 ----------
    if re.search(r"Math\.pow\s*\(", src) and re.search(r"lerp|damp", src):
        rep.ok("X21", "阻尼采用帧率无关写法")
    elif re.search(r"\*\s*0\.9\d*\b", src) and re.search(r"lerp", src):
        rep.warn("X21", "疑似固定系数阻尼",
                 "用 1 - Math.pow(k, dt) 而非固定 0.9，否则 120Hz 屏上快一倍")
    else:
        rep.ok("X21", "未发现帧率相关阻尼问题")

    # ---------- 16. 音效数量 ----------
    sfx_defs = count(r"function\s+(click|confirm|whoosh|impact|startAmbient|stopAmbient)\s*\(", src)
    if 0 < sfx_defs <= 10:
        rep.ok("X22", f"音效数量合理（{sfx_defs} 个合成函数）")
    elif sfx_defs > 10:
        rep.warn("X22", f"音效偏多（{sfx_defs} 个）",
                 "全站音效 ≤ 8 种，多了记不住")

    # ---------- 17. 键盘可达 ----------
    if re.search(r"keydown|keyup|tabindex|role=", src):
        rep.ok("X23", "有键盘 / 语义化支持")
    else:
        rep.warn("X23", "无键盘支持",
                 "至少给 Enter/Space 触发主交互，Esc 退出当前幕")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description="体验完整性静态自检")
    ap.add_argument("file", help="HTML 文件路径")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--strict", action="store_true", help="有警告也返回非零")
    args = ap.parse_args(argv)

    path = Path(args.file)
    if not path.exists():
        print(f"文件不存在：{path}", file=sys.stderr)
        return 2

    src = strip_comments(path.read_text(encoding="utf-8", errors="ignore"))
    rep = Report()
    check(src, rep)

    if args.json:
        print(json.dumps({
            "file": str(path),
            "size": len(src),
            "errors": rep.errors,
            "warnings": rep.warnings,
            "rows": rep.rows,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"体验完整性检查 · {path.name} · {len(src)} 字符\n")
        print(rep.render())

    if rep.errors:
        return 1
    if args.strict and rep.warnings:
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        sys.exit(0)
