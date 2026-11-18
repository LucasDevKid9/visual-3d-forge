"""视觉质量的契约测试。

这些不是截图比对——截图在 CI 里不可靠（字体、驱动、GPU 都不同），
同一份代码在 SwiftShader 和真机上出的图能差出 30%。

所以守的是**结构**：只要结构在，质感不会一夜回到解放前。
每一条都对应一次真实翻车，注释里写清是哪一次。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWER = ROOT / "spec" / "runtime" / "viewer.js"
OUT = ROOT / "spec" / "out"


def src() -> str:
    return VIEWER.read_text(encoding="utf-8")


# ── 接触阴影 ──────────────────────────────────────────────────────────


def test_depth_pass_uses_its_own_layer() -> None:
    """深度通道必须走独立 layer，不能靠临时改 visible。

    翻车记录：第一版用「渲染前把地面/网格藏起来，渲染后还原」，
    爆炸动画每帧触发一次 markDirty，隐藏/还原被打断，
    结果地面在某一帧之后永久消失。layer 是声明式的，没有还原这一步。
    """
    s = src()
    assert "CS_LAYER" in s
    assert "cam.layers.set(CS_LAYER)" in s
    assert "o.layers.enable(CS_LAYER)" in s


def test_ortho_far_leaves_margin() -> None:
    """正交相机 far 必须比物体高度大。

    翻车记录：far 正好取 height 时，物体底面精确落在远平面上，
    归一化深度与「空」同为 1.0，深度图里两者分不开，影子整片消失。
    找这个 bug 花的时间比写这套阴影还长——因为它「什么都对，就是没有」。
    """
    s = src()
    m = re.search(r"const camFar = height \* ([\d.]+)", s)
    assert m, "找不到 camFar 的定义"
    assert float(m.group(1)) > 1.15, "far 余量不足 15%，深度图会分不清底面与空"


def test_ground_is_a_visible_plate() -> None:
    """地面必须是有底色的材质，不能只画影子。

    翻车记录：照搬 three.js 的 ShadowMaterial 地面（只显示阴影、不显示面），
    影子渲对了却完全看不见——黑影子叠在近黑背景上，
    #121110 乘 0.38 还是黑。落地感的前提是地面存在。
    """
    s = src()
    assert "new THREE.ShadowMaterial" not in s, "ShadowMaterial 只画影不画面，影子无处可落"
    assert "uBase" in s, "地面缺少底色 uniform"


def test_sampling_is_jittered() -> None:
    """接触阴影的采样必须逐像素抖动。

    翻车记录：16 个固定螺旋采样点，在半径偏小时显出等距环纹，
    看起来像地上有一圈水波。抖动把环纹换成噪点，噪点会被人眼读成颗粒。
    """
    s = src()
    assert "gl_FragCoord" in s, "采样缺逐像素抖动，会出环纹"
    assert "jitter" in s


def test_shadow_alpha_uses_hit_rate_not_mean_depth() -> None:
    """遮蔽强度必须由命中率决定，不能是平均深度。

    翻车记录：第一版 `occ /= N` 之后再平方，边界处只命中一两个采样点时
    occ≈0.1，平方后 0.01，透明度 1%——影子在数学上存在、在屏幕上不存在。
    """
    s = src()
    assert "smoothstep(0.0, 0.50, hit)" in s or "smoothstep(0.0, 0.5, hit)" in s


# ── 环境与材质 ────────────────────────────────────────────────────────


def test_env_rig_has_narrow_light_tubes() -> None:
    """环境光棚里必须有窄而亮的光管。

    翻车记录：第一版 4 块接近正方形的面板，曲面上的高光糊成一团，
    金属读起来是灰塑料。金属之所以像金属，靠的是被拉成一条线的**结构**高光；
    这需要「面积小、亮度高」的灯，而不是「面积大、亮度中等」的面板。
    """
    s = src()
    m = re.search(r"const panels = \[(.*?)\];", s, re.S)
    assert m, "找不到环境光棚的面板表"
    block = m.group(1)
    panels = re.findall(r"\[([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*\[", block)
    assert len(panels) >= 6, f"光棚只有 {len(panels)} 块面板，不足以产生结构高光"

    narrow = [
        (float(w), float(h), float(d)) for w, h, d in panels
        if sorted([float(w), float(h), float(d)])[0] <= 0.1
    ]
    assert len(narrow) >= 2, "至少要有两条细长灯（有一个维度 ≤ 0.1）"


def test_materials_carry_env_intensity() -> None:
    """每个材质都要有 envMapIntensity。

    翻车记录：只调 metalness 不调 envMapIntensity，深色阳极件会一直是死黑——
    金属的明暗几乎全来自环境反射，环境强度就是它的「曝光」。
    """
    s = src()
    block = re.search(r"const MATERIALS = \{(.*?)\n\};", s, re.S)
    assert block, "找不到材质表"
    rows = [ln for ln in block.group(1).splitlines() if "{" in ln and "color" in ln]
    assert len(rows) >= 6, f"材质只有 {len(rows)} 条"
    for ln in rows:
        name = ln.strip().split(":")[0]
        assert "envIntensity" in ln, f"{name} 缺 envIntensity，暗色金属会变成死黑"


def test_front_fill_follows_camera() -> None:
    """正面补光必须跟随相机，否则朝向观众的那一面是死黑。

    那一面恰好是观众唯一在看的面。强度必须低（<0.5），
    高了就把体积压平，变成一张贴图。
    """
    s = src()
    assert "front.position.copy(camera.position)" in s
    m = re.search(r"DirectionalLight\(0x[0-9a-fA-F]+,\s*([\d.]+)\);\s*\n\s*scene\.add\(front\)", s)
    assert m, "找不到正面补光"
    assert float(m.group(1)) < 0.5, "补光强度过高，会压平体积"


# ── 清理 ──────────────────────────────────────────────────────────────


def test_no_shadow_map_without_receiver() -> None:
    """没有 receiveShadow 的对象时，shadow map 必须关掉。

    2048² 的阴影贴图每帧白渲，而场景里没有任何面接收它。
    这不是「优化」，是「别做无用功」。
    """
    s = src()
    if "receiveShadow = true" not in s:
        assert "shadowMap.enabled = false" in s, "没有接受者却还开着 shadow map"


def test_no_debug_hooks_in_output() -> None:
    """产物里不许留调试出口。

    排障时加过 window.__v3fDebug / __v3fHit / __v3fPaint：
    它们能把深度图读回、把 hit 值画成灰度——那是找到 bug 的唯一办法。
    但它们是手术刀，不是器官，缝上就该取出来。
    """
    s = src()
    assert "__v3f" not in s, "viewer.js 里还留着调试出口"
    if OUT.exists():
        for f in OUT.glob("*.html"):
            assert "__v3f" not in f.read_text(encoding="utf-8"), f"{f.name} 里还留着调试出口"
