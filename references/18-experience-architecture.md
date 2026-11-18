# 18 · 体验架构（Experience Architecture）

> **适用于体验型与混合型产物。**
> 确认件是**展示型**（判定见 [`../guide/06-EXPERIENCE.md`](../guide/06-EXPERIENCE.md)），只取本文的「幕数决策表」与「加载即第一章」两条，其余不适用。

> 本文件解决一个问题：**为什么同样用 three.js，有人做出产品说明书，有人做出 Awwwards 提名作品。**
> 差距不在渲染，在结构。

---

## 一、三个真实样本的骨架（逆向证据）

### 样本 A：F\*MMXX（Acidbeat + Gloom + Spite，2021 新年作品）

| 层 | 内容 |
|---|---|
| 入口 | `Choose a quality: low / medium / high / ultra` → 用户先选"档位" |
| 门槛 | `SFW / NSFW` 内容分级 |
| 加载 | `Loading... 0%` 显式进度 |
| 引导 | `Ring my bell to start` —— 一句话，一个动作，一个隐喻 |
| 内容 | WebGL 实时场景（Blender 资产 + three.js） |
| 收尾 | `Happy 2021` + 三人署名 |
| 前置 | 癫痫警告（accessibility 前置，不是免责声明堆在页脚） |

**结构特征**：档位 → 分级 → 加载 → 引导 → 体验 → 署名。**六段，一段不缺。**

### 样本 B：EXPERIENCE FUNTECH CREATIVITY（FunTech Inc.，2026）

Awwwards 官方描述原文：

> Explore FunTech's creativity with Fun-kun. **Instead of scrolling, clear ten real-time 3D scenes, each with its own interaction.** Built with three.js WebGPU/TSL, sound locked to 174 BPM.

十幕（Awwwards Elements 实录）：

| # | 幕名 | 交互动词 |
|---|---|---|
| 01 | Boot terminal | 开机 / 输入 |
| 02 | Render passes | 观察 / 切换通道 |
| 03 | Sticker storm | 拍打 / 撕扯 |
| 04 | Museum entrance | 进入 |
| 05 | Gallery walk | 行走 / 移动 |
| 06 | WE ARE FUNTECH. | 阅读（唯一纯静止幕） |
| 07 | Hold to dance | **按住**（持续输入） |
| 08 | Knock, knock | **敲击** |
| 09 | Eight worlds | 选择 / 穿越 |
| 10 | The page shatters | 破坏（终局） |
| — | End card | 收束 |

页面上的元信息：`The film · 49.66 s · 174 BPM`、`SOUND OFF` 开关、`JA / EN`、`Turn your phone sideways`。

**结构特征**：
- **反滚动**（Instead of scrolling）——用"通关"替代"浏览"
- **每幕一个动词**，且动词不重复：输入、观察、拍打、进入、行走、阅读、按住、敲击、选择、破坏
- **声音锁定 BPM**，49.66 秒 ≈ 36 小节（174 BPM × 4/4 → 每小节 1.379s）
- **100% AI 制作**（FunTech 官网自述），作者是"非工程师，用 vibe design 完成"

这条自述是本 Skill 存在的全部理由：**门槛不在写代码，在会不会设计结构。**

### 样本 C：LOIC PIX ARCADE（Loïc Picon，2026）

DOM 与 CSS 变量逆向出的机制：

| 机制 | 证据 |
|---|---|
| 街机叙事 | `LOIC PIX ARCADE` / `HIGH SCORES` / `arcade-scoreboard-in` / `arcade-rank-in` / `arcade-bravo-in` |
| 关卡化 | `data-gauntlet-entry` / `-asset` / `-construction` / `loading-gauntlet-bloom` |
| 序列分段 | `sequence7-dialogue-in` / `sequence7-training-progress`（至少 7 段，第 7 段是训练关） |
| QTE 系统 | `--qte-progress` / `--qte-target` / `--qte-timing-color` / `--qte-radius` |
| 节奏系统 | `--rhythm-accent` / `--rhythm-number-size` / `--cursor-beat` |
| 判定系统 | `--judge-color` / `--judge-duration` / `--judge-shake` / `--judge-tilt`（音游式 Perfect/Great） |
| 连击与蓄力 | `is-combo` / `is-charge-target` / `is-armed` / `is-earned` / `is-bonus` |
| 结算 | `arcade-player-result` / `-stars` / `is-current-player` |
| 运行时分级 | `data-performance-profile` / `-reason` / `-source` / `data-runtime-diagnostic-count` |
| 预烘焙 | `bake-player` / `bake-canvas` |
| 移动端守卫 | `mobile-orientation-guard` |

**结构特征**：这不是"作品集网站"，**这是一个用 Web 技术做的街机游戏，内容是 3D 作品**。
访客 = 玩家，作品 = 关卡，浏览 = 通关，欣赏 = 得分。

---

## 二、六段式：所有体验的共同骨架

不管做品牌站、产品发布、数据叙事还是个人作品集，**缺任何一段都会塌**：

```
GATE → ONBOARDING → JOURNEY → CLIMAX → RESOLUTION → REMNANT
```

| 段 | 作用 | 失败表现 | 最小实现 |
|---|---|---|---|
| **GATE** 门槛 | 建立预期 + 拿到授权（性能/声音/内容分级） | 一进来就卡、就响、就吓人 | 档位选择 / 声音开关 / 一句承诺 |
| **ONBOARDING** 引导 | 教会唯一必需的动作 | 用户不知道能点、能拖、能按 | 一个动词 + 一次示范 + 可跳过 |
| **JOURNEY** 旅程 | 主内容，分段推进 | 一屏到底、没有推进感 | ≥3 幕，每幕一个动词 |
| **CLIMAX** 高潮 | 情绪峰值，全片最贵的一秒 | 全程平、没有记忆点 | 一次规模突变 / 一次视角突变 / 一次破坏 |
| **RESOLUTION** 收束 | 把体验收进一句话 | 突然没了、不知道结束了 | 定格 + 一句人话 |
| **REMNANT** 痕迹 | 带走的东西 | 关掉就忘 | 分数 / 生成物 / 一句可复述的话 |

**自检**：拿这六格填，填不满三格以上就别开写代码。

---

## 三、十幕法：把旅程切成可执行的幕

样本 B 用十幕。**不是所有项目都要十幕**，但每条幕必须满足三个约束：

### 约束 1：一幕一个动词，动词不重复

动词清单（按认知负荷从低到高）：

```
看 → 转 → 点 → 拖 → 按 → 敲 → 划 → 摇 → 喊 → 吹 → 组合
```

同一动词连续出现两幕 = 节奏塌陷。第 7 幕"按住"和第 8 幕"敲击"相邻，正是为了避免重复。

### 约束 2：一幕一个"唯一焦点"

每幕只允许一个视觉主体 + 一个交互目标。屏幕上同时出现两个可点物 = 用户犹豫 = 节奏断。

### 约束 3：幕间必须有转场，且转场有名字

见 `19-rhythm-and-timeline.md` 的转场类型学。转场不是"淡入淡出"，是**叙事标点**。

### 幕数决策表

| 内容量 | 建议幕数 | 单幕时长 | 总时长 |
|---|---|---|---|
| 单一物体展示 | 3 幕（呈现 / 拆解 / 收束） | 6–10s | 20–30s |
| 产品发布 | 5–7 幕 | 8–15s | 50–90s |
| 品牌体验 | 8–12 幕 | 6–12s | 60–120s |
| 数据叙事 | 5–9 幕 | 10–20s | 80–150s |
| 可玩作品集 | 7–12 关 | 不定（玩家控制） | 3–8min |

**超过 12 幕**：拆成"章节"，每章 3–4 幕，章间给一次"呼吸"（静止画面 + 一句文案）。

---

## 四、状态机：体验的骨架是有限状态机，不是时间轴

时间轴（timeline）只能做"播完就完"。真正的体验是**状态机**：状态 + 事件 + 转移 + 守卫。

### 最小状态机

```
IDLE → GATE → LOADING → READY → SCENE_01 … SCENE_N → CLIMAX → OUTRO → END
                    ↑                                    ↓
                    └──────────── 重玩 / 回看 ────────────┘
```

### 必备的四条边

| 边 | 为什么必须有 |
|---|---|
| `LOADING → READY` 守卫：资源就绪 + 用户已交互 | 避免"没加载完就开始播" |
| `任意 → PAUSED`（失焦 / 切标签页） | 后台不停渲染 = 烧电 + 回来时间错乱 |
| `任意 → SKIP → OUTRO` | 用户有权跳过。没有跳过 = 绑架 |
| `OUTRO → GATE` 重玩 | 可重入才有传播 |

### 实现要点

```js
const MACHINE = {
  state: 'GATE',
  scenes: [],          // 幕表，每项 { id, verb, enter, exit, duration }
  index: 0,
  history: [],         // 用于回看
  listeners: new Set(),

  can(next) {          // 守卫
    if (next === 'SCENE' && !this.assetsReady) return false;
    if (this.locked) return false;
    return true;
  },
  go(next, payload) {
    if (!this.can(next)) return false;
    const prev = this.state;
    this.scenes[this.index]?.exit?.();
    this.state = next;
    this.scenes[this.index]?.enter?.(payload);
    this.emit({ from: prev, to: next, payload });
    return true;
  },
  emit(e) { this.listeners.forEach(fn => fn(e)); },
  on(fn) { this.listeners.add(fn); return () => this.listeners.delete(fn); }
};
```

**硬要求**：状态变更必须走 `go()`，禁止在事件回调里直接改 `state`。否则一定出现"两个幕同时活着"的幽灵状态。

### 幕的生命周期契约

每一幕必须成对实现：

```js
{
  id: 'knock',
  verb: 'knock',              // 动词，用于引导文案与音效
  hint: '敲敲门',              // 屏幕上的一句话，≤8 字
  duration: 8.0,              // 期望时长（秒），用于进度与自动推进
  enter() { /* 建场景、亮灯、挂事件 */ },
  update(dt, t) { /* 每帧，只做与幕相关的 */ },
  exit() { /* 撤事件、停音、清临时对象 */ }
}
```

`exit()` 不干净 = 内存泄漏 + 音效叠音 + 事件串台。这是最常见的体验崩坏点。

---

## 五、三层引擎：本 Skill 的总体架构

```
┌─────────────────────────────────────────────┐
│  L0  意图层    G0 载体 / G1 意图 / G2 参考 / G3 预算 │
├─────────────────────────────────────────────┤
│  L1  体验层 ★ 六段式 · 十幕法 · 状态机 · 节奏 · 声音 · 反馈 │  ← v3.0 新增
├─────────────────────────────────────────────┤
│  L2  造物层    几何 · 材质 · 光照 · 运动 · 交互          │
├─────────────────────────────────────────────┤
│  L3  工程层    性能分级 · 降级 · 离线 · 交付形态         │
└─────────────────────────────────────────────┘
```

**关键原则：L1 决定 L2。**
先定"第 7 幕要按住跳舞"，再决定"跳舞用什么几何、什么材质、什么光"。
反过来做（先建模型再想怎么用）必然产出"好看的模型摆在中间慢慢转"。

**禁止的顺序**：建模 → 摆场景 → 想交互 → 加 UI。
**要求的顺序**：写剧本 → 切幕 → 定动词 → 定镜头 → 定节奏 → 才建模。

---

## 六、三个反直觉结论

### 1. 动画越多越平

样本 C 有 44 个 `@keyframes`，但其中 30 个是**微反馈**（按钮呼吸、字母抖动、数字跳动），只有 14 个是**叙事转场**。
微反馈负责"活着"，叙事转场负责"推进"。**两者混用 = 全程都在动 = 什么都不突出。**

配比建议：微反馈 : 叙事转场 ≈ 2 : 1。

### 2. 加载不是等待，是第一章

样本 A 显式显示 `Loading... 0%`；样本 C 把加载做成 `loading-gauntlet-bloom`（试炼绽放）；样本 B 用 `Boot terminal` 当第一幕。

三种做法，同一个判断：**加载期是用户注意力最集中的时刻，浪费它等于浪费开场。**

### 3. 声音不是加分项，是节拍器

样本 B 直接标注 `174 BPM`。这不是炫技，是**把所有动效时长对齐到同一个时间栅格**：

```
1 拍 = 60 / 174 = 0.3448 s
1 小节(4/4) = 1.3793 s
49.66 s ≈ 36 小节
```

所有转场时长取 `0.345 / 0.69 / 1.379 / 2.759` 秒的整数倍，画面自然"合拍"。
**没有声音也要按这个栅格排**——视觉节奏的底层是时间量化。

---

## 七、本文件的执行位置

| 阶段 | 用本文件做什么 |
|---|---|
| P0 意图 | 用六段式填表，填不满就回问用户 |
| P1 剧本 | 用十幕法切幕，写幕表（id / verb / hint / duration） |
| P2 分镜 | 每幕定一个唯一焦点 + 一个镜头 |
| P3 建模 | 按幕建模，一幕只建它需要的 |
| P4 装配 | 实现状态机，接幕生命周期 |
| P5 验收 | 走六段式自检 + 十幕动词不重复检查 |

详见 `19-rhythm-and-timeline.md`（节奏）、`20-sound-and-feedback.md`（声音与反馈）、`21-game-feel-and-guidance.md`（游戏感与引导）。
