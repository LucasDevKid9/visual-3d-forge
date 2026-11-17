# 07 性能与降级

目的：保证页面在任何设备上都能打开、能操作。一个掉帧的页面等于没做。

## 预算表（按交付档）

| 项 | 桌面 | 移动 | 超限动作 |
| --- | --- | --- | --- |
| 三角面 | 150k | 60k | 触发 LOD / 减面 |
| 绘制调用 | 200 | 120 | 合批 / 实例化 |
| 纹理总量 | 32MB | 16MB | 降分辨率 / 换程序化 |
| 单贴图边长 | 2048 | 1024 | 降为 1024/512 |
| 首帧时间 | < 1.2s | < 2s | 分帧构建 + 占位 |
| 目标帧率 | 60fps | 30fps | 先降画质 |

**估算方法（不实测也能用）**：
```
三角面 ≈ 部件数量 × 每件平均面数
绘制调用 ≈ 独立材质数 × 独立几何数（实例化后按 1 计）
```

## 必须内建的五个机制

### 1. 像素比封顶
```js
const dpr = Math.min(devicePixelRatio, isMobile ? 1.5 : 2);
renderer.setPixelRatio(dpr);
```

### 2. 自适应降级（自动，不是手动）
连续 30 帧平均帧时间 > 20ms（≈50fps）就降一档，按 SKILL.md 的降级阶梯顺序执行，每次只降一档，降到底就停。
不要「降帧率保画质」，卡顿比画质差更毁体验。

### 3. 后台暂停
```js
document.addEventListener('visibilitychange', () => {
  if (document.hidden) { running = false; }
  else { running = true; clock.getDelta(); requestAnimationFrame(tick); }
});
```
不可见的标签页不要跑渲染循环——这是最常见的电老虎。

### 4. 首帧占位
重活（模型解析、贴图生成、Marching Cubes）先给一个低模/纯色占位 + 进度提示，算完替换。不要让人对着白屏 3 秒。

### 5. 资源生命周期
切换视图/部件时释放 geometry 与 texture：
```js
geo.dispose(); mat.dispose(); tex.dispose();
```
不释放会在多次切换后爆显存（尤其手机上）。

## 降级阶梯（严格按顺序，每次一档）

1. 关后处理（bloom / AO / DOF）→ 省 20–40% 帧时间
2. 像素比 2 → 1.5 → 1.0
3. 阴影 2048 → 1024 → 关阴影改用接触阴影
4. 材质 `MeshPhysicalMaterial` → `MeshStandardMaterial`（去 clearcoat/transmission）
5. 触发 LOD1（60% 面）
6. 关环境反射、降环境光强度
7. 粒子数量减半、群体数减半

**记录降级动作**，交付说明里写清「在弱设备上会自动降级到 X 档」。

## 移动端专项

- 触摸事件：`touchstart/move/end` 与 trackpad 行为不同，`OrbitControls` 已处理，别自写。
- 禁用双指缩放页面：`meta viewport user-scalable=no` + `touch-action: none` 在 canvas 上。
- 高度用 `100dvh`，不用 `100vh`（移动端地址栏会遮挡）。
- 慎用 `MeshPhysicalMaterial` 的 `transmission`（真实折射很贵，移动端改用 opacity + 环境贴图近似）。

## 无 WebGL 兜底（必须写）

```js
function hasWebGL() {
  try {
    const c = document.createElement('canvas');
    return !!(window.WebGLRenderingContext && (c.getContext('webgl2') || c.getContext('webgl')));
  } catch (e) { return false; }
}
```
失败时展示：静态主视图（SVG 等距图或一张渲染截图）+ 一句说明 + 关键信息（尺寸/工序/参数）。**绝不留白屏。**

## 常见性能陷阱

| 现象 | 真实原因 | 修复 |
| --- | --- | --- |
| 移动端发烫 | 像素比 3 + 阴影 + 后处理 | 三项依次降 |
| 切回标签页后画面跳变 | dt 累积 | `Math.min(dt, 1/30)` |
| 内存持续上涨 | 每次切换重建几何不释放 | dispose + 复用 |
| 首帧卡 3 秒 | 同步解析大模型/生成大贴图 | 分帧 + 占位 |
| 拾取时明显卡顿 | 每帧 raycast 全场景 | 仅 pointerup 拾取 + 包围球预判 |
| 文字/线条闪烁 | 深度冲突 | 给 UI 线框 `polygonOffset` 或改用 2D 覆盖层 |
