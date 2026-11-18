/* SpecViewer · IR → 场景
 *
 * 只做一件事：把 Spec-IR 渲染成一个能转、能剖、能量的确认件。
 * 它不知道图纸长什么样，也不做任何推断——所有判断在编译期已经做完，
 * 这里只执行。这是「确定性」的物理边界：同一个 IR，永远同一个画面。
 */
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const MM = 0.001;            // IR 用毫米，世界用米
const CLIP_AXIS = new THREE.Vector3(0, -1, 0);

/* ─────────────────────────── 材质 ─────────────────────────── */

const MATERIALS = {
  // 每个材质给四项：底色、金属度、粗糙度、环境强度。
  // 第四项容易被漏掉：它才是「这块金属有多亮」的开关。
  // 只调 metalness 不调 envMapIntensity，暗色阳极件会一直是死黑一片。
  cast_iron:      { color: 0x4d5157, metalness: 0.34, roughness: 0.70, envIntensity: 0.95 },
  steel:          { color: 0xb5bbc3, metalness: 0.98, roughness: 0.18, envIntensity: 1.30 },
  stainless:      { color: 0xc3c8ce, metalness: 0.98, roughness: 0.28, envIntensity: 1.18 },
  aluminum:       { color: 0xc6cad0, metalness: 0.94, roughness: 0.32, envIntensity: 1.15 },
  anodized_black: { color: 0x343a42, metalness: 0.74, roughness: 0.40, envIntensity: 1.55 },
  brass:          { color: 0xb08d57, metalness: 0.96, roughness: 0.26, envIntensity: 1.20 },
  copper:         { color: 0xa5603c, metalness: 0.96, roughness: 0.30, envIntensity: 1.15 },
  rubber:         { color: 0x16181a, metalness: 0.02, roughness: 0.94, envIntensity: 0.55 },
  pom_white:      { color: 0xd6d4cc, metalness: 0.00, roughness: 0.52, envIntensity: 0.85 },
};

const EVIDENCE_COLOR = {
  measured: 0x7fbf6a,
  inferred: 0xd9a24a,
  standard: 0x8a9199,
};

/* ─────────────────────────── 几何基元 ───────────────────────────
 * 约定：所有基元沿主轴从 0 开始向外长，单位米。
 * 这样装配链只需要一个累加器，不需要求包围盒反推位置。
 */

// 回转体天然沿 Y（Lathe 绕 Y 轴）；拉伸体天然沿 Z（depth 沿 Z）。
// 两者的对齐规则不同，不能共用一个函数——这是第一版踩过的坑。
function alignRevolve(geo, axis) {
  if (axis === 'x') geo.rotateZ(-Math.PI / 2);
  else if (axis === 'z') geo.rotateX(Math.PI / 2);
  return geo;
}
function alignExtrude(geo, axis) {
  if (axis === 'x') geo.rotateY(Math.PI / 2);
  else if (axis === 'y') geo.rotateX(-Math.PI / 2);
  return geo;
}

function buildRevolve(p, axis) {
  const pts = p.profile.map(([r, a]) => new THREE.Vector2(Math.max(r, 1e-4) * MM, a * MM));
  const g = new THREE.LatheGeometry(pts, p.segments || 64);
  return alignRevolve(g, axis);
}

function shapeFromOutline(o) {
  const s = new THREE.Shape(o.map(([x, y]) => new THREE.Vector2(x * MM, y * MM)));
  return s;
}

function buildExtrude(p, axis) {
  const shape = shapeFromOutline(p.outline);
  (p.holes || []).forEach((h) => {
    shape.holes.push(new THREE.Path(h.map(([x, y]) => new THREE.Vector2(x * MM, y * MM))));
  });
  const bevel = p.bevel || 0;
  const g = new THREE.ExtrudeGeometry(shape, {
    depth: p.depth * MM,
    bevelEnabled: bevel > 0,
    bevelSize: bevel * MM * 0.5,
    bevelThickness: bevel * MM * 0.5,
    bevelSegments: 2,
    curveSegments: 48,
  });
  return alignExtrude(g, axis);
}

function gearOutline(z, m) {
  const rp = (m * z) / 2;
  const ra = rp + m;
  const rd = Math.max(rp - 1.25 * m, 0.6);
  const step = (Math.PI * 2) / z;
  const pts = [];
  for (let i = 0; i < z; i++) {
    const a0 = i * step;
    // 齿根 → 齿顶 → 齿顶 → 齿根，四点一齿。够看清是齿轮，不必是真渐开线。
    pts.push([rd * Math.cos(a0), rd * Math.sin(a0)]);
    pts.push([ra * Math.cos(a0 + step * 0.20), ra * Math.sin(a0 + step * 0.20)]);
    pts.push([ra * Math.cos(a0 + step * 0.46), ra * Math.sin(a0 + step * 0.46)]);
    pts.push([rd * Math.cos(a0 + step * 0.66), rd * Math.sin(a0 + step * 0.66)]);
  }
  return pts;
}

function buildGear(p, axis) {
  const outline = gearOutline(p.z, p.m);
  const holes = [];
  if (p.bore > 0) {
    const seg = 32;
    const ring = [];
    for (let i = 0; i < seg; i++) {
      const a = (i / seg) * Math.PI * 2;
      ring.push([(p.bore / 2) * Math.cos(a), (p.bore / 2) * Math.sin(a)]);
    }
    holes.push(ring);
  }
  return buildExtrude(
    { outline, holes, depth: p.thickness, bevel: 0 },
    axis,
  );
}

function buildPrimitive(p) {
  if (p.shape === 'box') {
    return new THREE.BoxGeometry(p.w * MM, p.h * MM, p.d * MM);
  }
  return new THREE.BoxGeometry(0.01, 0.01, 0.01);
}

function buildOne(spec) {
  const axis = spec.axis || 'x';
  switch (spec.kind) {
    case 'revolve': return buildRevolve(spec.params, axis);
    case 'extrude': return buildExtrude(spec.params, axis);
    case 'gear': return buildGear(spec.params, axis);
    case 'primitive': return buildPrimitive(spec.params);
    default: return new THREE.BoxGeometry(0.01, 0.01, 0.01);
  }
}

/* ─────────────────────────── 组装 ─────────────────────────── */

function buildPart(part, group) {
  const meshes = [];

  if (part.kind === 'pattern') {
    const { count, radius, phase = 0, proto } = part.params;
    for (let i = 0; i < count; i++) {
      const g = buildOne(proto);
      const m = new THREE.Mesh(g, null);          // 材质在下面统一挂
      const a = phase + (i / count) * Math.PI * 2;
      m.position.set(0, radius * MM * Math.sin(a), radius * MM * Math.cos(a));
      m.rotation.x = a;                           // 行星轮自转，齿面才有咬合感
      meshes.push(m);
    }
  } else {
    meshes.push(new THREE.Mesh(buildOne(part), null));
  }

  const preset = MATERIALS[part.material] || MATERIALS.steel;
  const mat = new THREE.MeshStandardMaterial({
    color: preset.color,
    metalness: preset.metalness,
    roughness: preset.roughness,
    envMapIntensity: preset.envIntensity ?? 1,
    side: THREE.DoubleSide,
    clippingPlanes: [],
    clipShadows: true,
  });

  const edgeMat = new THREE.LineBasicMaterial({
    color: EVIDENCE_COLOR[worstGrade(part.evidence)],
    transparent: true,
    opacity: 0.12,
    depthTest: true,
    clippingPlanes: [],
  });

  const holder = new THREE.Group();
  meshes.forEach((m) => {
    m.material = mat;
    m.castShadow = false;
    m.receiveShadow = false;
    m.userData.partUid = part.uid;
    holder.add(m);
    const edges = new THREE.LineSegments(new THREE.EdgesGeometry(m.geometry, 26), edgeMat);
    edges.userData.partUid = part.uid;
    holder.add(edges);
  });

  holder.position.set(part.transform.pos[0] * MM, part.transform.pos[1] * MM, part.transform.pos[2] * MM);
  if (part.transform.rot) {
    holder.rotation.set(...part.transform.rot.map((d) => (d * Math.PI) / 180));
  }
  holder.userData.partUid = part.uid;
  holder.userData.basePos = holder.position.clone();
  holder.userData.explode = new THREE.Vector3(...(part.explode || [0, 0, 0]));

  group.add(holder);
  return { holder, mat, edgeMat, meshes };
}

/** 一个零件里最「弱」的那一档成色，决定它描边的颜色 —— 诚实优先。 */
function worstGrade(evidence) {
  if (!evidence) return 'standard';
  const grades = Object.values(evidence).map((e) => e.grade);
  if (grades.includes('inferred')) return 'inferred';
  if (grades.includes('measured')) return 'measured';
  return 'standard';
}

/* ─────────────────── 舞台地面：底板 + 接触阴影（contact shadow） ───────────────────
 * 做法照 threejs.org/examples/webgl_shadow_contact：
 *   ① 俯视正交相机把零件的归一化深度渲进一张 RT（清成 1.0 = 远平面 = 空）
 *   ② 地面用这张图做黄金角螺旋抖动采样，得到贴着物体的一团柔和暗影
 *
 * 两处与示例不同，都是被真实渲染逼出来的：
 *
 * 【一】地面必须是可见的底板，不能是只显示影子的 ShadowMaterial。
 * 第一版照搬 ShadowMaterial，结果影子渲对了、却完全看不见——
 * 黑影子叠在近黑背景上，没有可压暗的余地。#121110 乘 0.38 还是黑。
 * 「落地感」的前提是地面存在；地面不存在，影子就无处安放。
 *
 * 【二】正交相机 far 必须留 1.4 倍余量。取满 height 时物体底面恰好落在
 * 远平面上，归一化后与「空」同为 1.0，深度图里分不开，影子整片消失。
 *
 * 为什么不用方向光的 shadowMap：确认件是「产品照」，不是「室外照」。
 * 斜射主光会在台面上拖出一条有硬边、有方向的长影——观众第一眼读到的是
 * 「几点钟的太阳」，而不是「这个件多大」。产品照里唯一的阴影，
 * 是物件正下方那一团。
 *
 * 用 layers 而不是临时改 visible：深度通道只认 layer 1，
 * 地面/网格/尺寸线不进这条路，渲染完不用还原任何状态。
 */
const CS_LAYER = 1;
const CS_SIZE = 1024;

function makeContactShadow(world, bbox, renderer, opts = {}) {
  const size = new THREE.Vector3();
  bbox.getSize(size);
  const maxDim = Math.max(size.x, size.y, size.z);
  // 余量要覆盖到「最大爆炸状态」，不只是初始装配态。
  // 按初始包围盒开窗口，爆炸后零件会跑出深度图，影子被硬切一刀。
  const pad = maxDim * (0.55 + 0.36 * 1.35);
  const span = Math.max(size.x, size.z) + pad * 2;
  const radius = maxDim * 2.1;
  const cx = (bbox.min.x + bbox.max.x) / 2;
  const cz = (bbox.min.z + bbox.max.z) / 2;
  const top = bbox.max.y + Math.max(maxDim * 0.5, 0.02);
  const bottom = bbox.min.y;
  const height = top - bottom;

  const rt = new THREE.WebGLRenderTarget(CS_SIZE, CS_SIZE, {
    minFilter: THREE.LinearFilter,
    magFilter: THREE.LinearFilter,
    format: THREE.RGBAFormat,
    type: THREE.HalfFloatType,
    depthBuffer: true,
    stencilBuffer: false,
  });

  const camFar = height * 1.4;
  const cam = new THREE.OrthographicCamera(-span / 2, span / 2, span / 2, -span / 2, 0, camFar);
  cam.position.set(cx, top, cz);
  cam.up.set(0, 0, -1);
  cam.lookAt(cx, bottom, cz);
  cam.layers.set(CS_LAYER);

  const depthMat = new THREE.ShaderMaterial({
    side: THREE.DoubleSide,
    vertexShader: `
      varying float vZ;
      void main() {
        vec4 c = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        vZ = c.z * 0.5 + 0.5;
        gl_Position = c;
      }`,
    fragmentShader: `
      varying float vZ;
      void main() { gl_FragColor = vec4(vZ, 0.0, 0.0, 1.0); }`,
  });

  const mat = new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    uniforms: {
      tD: { value: rt.texture },
      uC: { value: new THREE.Vector2(cx, cz) },
      uSpan: { value: span },
      uBlur: { value: Math.max(maxDim * (opts.blur ?? 0.062), 0.002) },
      uBias: { value: opts.bias ?? 0.90 },
      uR: { value: radius },
      uBase: { value: new THREE.Color(opts.base ?? 0x1b1815) },
      uShadow: { value: opts.shadow ?? 0.86 },
      uFade: { value: opts.fade ?? 0.94 },
    },
    vertexShader: `
      varying vec3 vW;
      void main() {
        vec4 wp = modelMatrix * vec4(position, 1.0);
        vW = wp.xyz;
        gl_Position = projectionMatrix * viewMatrix * wp;
      }`,
    fragmentShader: `
      varying vec3 vW;
      uniform sampler2D tD;
      uniform vec2 uC;
      uniform float uSpan, uBlur, uBias, uR, uShadow, uFade;
      uniform vec3 uBase;

      void main() {
        // 底板径向淡出：边缘融进背景，读起来是「无限地面」而不是一个圆饼
        float d2 = length(vW.xz - uC);
        float edge = 1.0 - smoothstep(uR * 0.40, uR, d2);
        if (edge < 0.004) discard;

        vec2 uv = vec2((vW.x - uC.x) / uSpan + 0.5, (uC.y - vW.z) / uSpan + 0.5);

        float hit = 0.0;
        if (uv.x > 0.0 && uv.x < 1.0 && uv.y > 0.0 && uv.y < 1.0) {
          // 逐像素旋转采样：固定螺旋在稀疏采样下会显出等距环纹，
          // 看着像「地上有水波」。抖动把环纹换成噪点，噪点会被人眼当成颗粒。
          float jitter = fract(sin(dot(gl_FragCoord.xy, vec2(12.9898, 78.233))) * 43758.5453);
          for (int i = 0; i < 24; i++) {
            float fi = float(i);
            float a = fi * 2.39996323 + jitter * 6.2831853;
            float r = sqrt((fi + 0.5) / 24.0) * uBlur;
            float d = texture2D(tD, uv + vec2(cos(a), sin(a)) * r / uSpan).x;
            hit += 1.0 - smoothstep(uBias, 1.0, d);
          }
          hit /= 24.0;
        }

        // 命中率 0.5 以上给满：物体正下方必满，边缘自然渐隐
        float shade = smoothstep(0.0, 0.50, hit);
        vec3 col = uBase * (1.0 - shade * uShadow);
        gl_FragColor = vec4(col, edge * uFade);
      }`,
  });

  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(radius * 2, radius * 2), mat);
  mesh.rotation.x = -Math.PI / 2;
  mesh.position.set(cx, bottom + 0.0002, cz);
  mesh.renderOrder = 1;

  world.traverse((o) => { if (o.isMesh) o.layers.enable(CS_LAYER); });

  let dirty = true;
  function render() {
    const prevTarget = renderer.getRenderTarget();
    const prevClear = renderer.getClearColor(new THREE.Color());
    const prevAlpha = renderer.getClearAlpha();
    renderer.setRenderTarget(rt);
    renderer.setClearColor(0xffffff, 1);
    renderer.render(world, cam);
    renderer.setRenderTarget(prevTarget);
    renderer.setClearColor(prevClear, prevAlpha);
    dirty = false;
  }

  return {
    mesh,
    material: mat,
    rt,
    markDirty() { dirty = true; },
    update() { if (dirty) render(); },
    render,
  };
}

/* ─────────────────────────── UI ─────────────────────────── */

function el(tag, cls, html) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html != null) n.innerHTML = html;
  return n;
}

function buildShell(IR) {
  const root = document.body;
  root.innerHTML = '';

  const stage = el('div', 'sv-stage');
  const canvas = el('canvas', 'sv-canvas');
  stage.appendChild(canvas);

  const head = el('header', 'sv-head');
  head.innerHTML = `
    <div class="sv-kicker">装配确认件 · 非生产模型</div>
    <h1>${IR.title}</h1>
    <p class="sv-sub">${IR.subtitle || ''}</p>
    <p class="sv-note">${(IR.source && IR.source.note) || '尺寸来源见右下明细。'}</p>
  `;

  const legend = el('div', 'sv-legend');
  const counts = IR.report.counts;
  const cov = Math.round(IR.report.coverage * 100);
  legend.innerHTML = `
    <div class="sv-bar"><i style="width:${cov}%"></i></div>
    <div class="sv-cov">证据覆盖率 <b>${cov}%</b> · 实测 ${counts.measured} / 推断 ${counts.inferred} / 标准 ${counts.standard}</div>
    <ul>
      <li><s class="g-m"></s>图上标注</li>
      <li><s class="g-i"></s>推断得出</li>
      <li><s class="g-s"></s>标准件</li>
    </ul>
  `;

  const panel = el('aside', 'sv-panel');
  panel.innerHTML = `<div class="sv-panel-h">构件明细 <span>${IR.parts.length}</span></div>`;

  const list = el('div', 'sv-list');
  IR.parts.forEach((p) => {
    const row = el('div', 'sv-row');
    row.dataset.uid = p.uid;
    const evs = Object.entries(p.evidence || {});
    row.innerHTML = `
      <div class="sv-row-h"><span class="sv-dot ${worstGrade(p.evidence)}"></span>${p.label}<em>${p.kind}</em></div>
      <dl>${evs.map(([k, v]) => `
        <dt class="${v.anchor ? 'loc' : ''}">${k}</dt>
        <dd class="${v.grade}" data-ev="${k}" title="${v.anchor ? '点击在模型上定位' : '此项未在几何上定位'}">${v.value}<small>${v.src || ''}</small></dd>
      `).join('')}</dl>
    `;
    list.appendChild(row);
  });
  panel.appendChild(list);

  const dock = el('div', 'sv-dock');
  dock.innerHTML = `
    <div class="sv-group" data-g="views">
      ${(IR.views || []).map((v) => `<button data-view="${v.kind}">${v.label || v.kind}</button>`).join('')}
    </div>
    <label class="sv-slider"><span>爆炸</span><input type="range" min="0" max="100" value="0" data-k="explode"><b>0%</b></label>
    <label class="sv-slider"><span>剖切</span><input type="range" min="0" max="100" value="0" data-k="section"><b>关</b></label>
    <div class="sv-actions">
      <button class="sv-ghost on" data-act="dims">尺寸</button>
      <button class="sv-ghost" data-act="reset">复位</button>
    </div>
  `;

  const foot = el('div', 'sv-foot');
  foot.innerHTML = `
    <span class="sv-stamp">IR ${IR.ir_version} · ${IR.grade || ''}</span>
    <span>这是一份确认件，不是模型。要改？导出起稿交给建模师。</span>
  `;

  root.append(stage, head, legend, panel, dock, foot);
  return { canvas, stage, panel, list, legend, dock };
}

/* ─────────────────────────── 主程序 ─────────────────────────── */

function hasWebGL() {
  try {
    const c = document.createElement('canvas');
    return !!(window.WebGLRenderingContext
      && (c.getContext('webgl2') || c.getContext('webgl') || c.getContext('experimental-webgl')));
  } catch (e) {
    return false;
  }
}

/** 没有 WebGL 时给一句人话，而不是一片白。 */
function renderNoWebGL(IR) {
  document.body.innerHTML = `
    <div class="sv-nowebgl">
      <div class="sv-kicker">装配确认件 · 未渲染</div>
      <h1>${IR.title}</h1>
      <p>这个浏览器没有可用的 WebGL，三维视图无法启动。</p>
      <p class="sv-nowebgl-why">常见原因：浏览器的硬件加速被关闭、显卡驱动过旧，
         或者这台设备本身不支持 WebGL。这不是文件损坏——换一个浏览器，
         或在设置里打开「使用硬件加速」，再打开本文件即可。</p>
      <p class="sv-nowebgl-note">尺寸与结论不受影响：所有数值、成色与检查项都在
         <b>${IR.id}.report.html</b> 里，那是一份纯 HTML 报告，不需要 WebGL。</p>
    </div>`;
}

function boot(IR) {
  // 先探再建。WebGLRenderer 构造失败会抛异常，页面白屏且没有任何解释——
  // 用户看到的是「你们的东西打不开」，而不是「你的浏览器没开硬件加速」。
  if (!hasWebGL()) {
    renderNoWebGL(IR);
    return;
  }

  const ui = buildShell(IR);

  // ── 动效常量：全站同源 ────────────────────────────────────────────
  // 时长不再散落在各处当魔数。取 120 BPM 的整数拍，相机与转场自然合拍；
  // 即使确认件没有声音，视觉节奏的底层也是时间量化。
  const MOTION = (() => {
    const BPM = 120;
    const beat = 60 / BPM;                       // 0.5 s
    const snap = (s, sub = 2) => Math.round(s / (beat / sub)) * (beat / sub);
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    return {
      bpm: BPM, beat, snap, reduce,
      fly: 500,                                  // = 1 拍，原来散落写成 620
      // 减少动态：时长压到 1/4，而不是 0 —— 状态变化仍要看得见，只是不晃。
      dur: (ms) => (reduce ? Math.max(80, Math.round(ms / 4)) : ms),
      easeOutCubic: (k) => 1 - Math.pow(1 - k, 3),
      easeInOutCubic: (k) => (k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2),
    };
  })();

  const renderer = new THREE.WebGLRenderer({ canvas: ui.canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  // 阴影贴图关掉：地面改成接触阴影那一张 shader 之后，场景里没有一个
  // receiveShadow 的对象，2048² 的 shadow map 每帧白渲。省下的是真实的帧时间。
  renderer.shadowMap.enabled = false;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.12;
  renderer.localClippingEnabled = true;

  const scene = new THREE.Scene();
  scene.fog = new THREE.Fog(0x121110, 1.6, 4.2);

  const camera = new THREE.PerspectiveCamera(36, 1, 0.01, 60);

  // ── 环境：一间柔光棚 ──
  // 金属之所以「像金属」，不是因为 metalness=1，是因为它反射的东西有结构。
  // 一张均匀的 HDRI 只能把金属变成灰塑料；真正起作用的是**窄而亮的光带**——
  // 它们会在曲面上被拉成一条条高光，人眼靠这组高光读「这是金属，而且是磨过的」。
  //
  // 第一版只有 4 块面板，且都接近正方形：曲面上的高光糊成一团，读起来是塑料。
  // 这一版换成「宽顶棚 + 两条窄灯带 + 地面反光板」，并让左右色温不同——
  // 冷侧暖侧的差异会在圆柱侧壁上形成一道明暗过渡，体积感是这么来的。
  const pmrem = new THREE.PMREMGenerator(renderer);
  const envScene = new THREE.Scene();
  envScene.add(new THREE.Mesh(
    new THREE.BoxGeometry(10, 7, 10),
    new THREE.MeshBasicMaterial({ color: 0x0b0d10, side: THREE.BackSide }),
  ));

  // [w, h, d, [x,y,z], intensity, hex]
  const panels = [
    [4.6, 0.02, 4.6, [0, 3.35, 0], 1.95, 0xfff6ea],      // 顶部主柔光
    [0.035, 3.0, 3.4, [-4.9, 0.5, 0.5], 3.2, 0xffe6c4],  // 左侧暖灯带
    [0.035, 2.4, 3.0, [4.9, 0.3, -0.9], 1.9, 0xc2d6ff],  // 右侧冷灯带
    [3.2, 0.02, 0.05, [0, 1.35, -4.9], 1.3, 0xd6e2ff],   // 背后水平轮廓条
    [4.2, 0.02, 4.2, [0, -3.4, 0], 0.42, 0x3a2b1c],      // 地面暖反光
    // 两条「光管」：沿 X 延伸的细长灯。它们被圆柱面反射成一条水平亮线，
    // 而人眼判「这是金属」靠的就是这条线。面积小、亮度高，总能量并不大，
    // 所以不会过曝；换成大面积高亮只会把圆柱打成一团白。
    [3.6, 0.055, 0.055, [0, 1.98, 4.55], 7.0, 0xfff3e0],
    [3.2, 0.05, 0.05, [0, 2.45, -4.45], 3.4, 0xd9e6ff],
  ];
  panels.forEach(([w, h, d, pos, k, hex]) => {
    const m = new THREE.Mesh(
      new THREE.BoxGeometry(w, h, d),
      new THREE.MeshBasicMaterial({ color: new THREE.Color(hex).multiplyScalar(k) }),
    );
    m.position.set(...pos);
    envScene.add(m);
  });

  const envRT = pmrem.fromScene(envScene, 0.035);
  scene.environment = envRT.texture;
  scene.environmentIntensity = 1.05;

  // 三光：主光有阴影，补光冷，轮廓光从背后切边
  scene.add(new THREE.HemisphereLight(0x9fb0c8, 0x231d18, 0.72));

  const key = new THREE.DirectionalLight(0xfff2e0, 1.95);
  key.position.set(1.8, 2.4, 1.5);
  scene.add(key);

  const fill = new THREE.DirectionalLight(0x9aabc4, 0.48);
  fill.position.set(-1.6, 0.9, -1.2);
  scene.add(fill);

  const rim = new THREE.DirectionalLight(0xffd9a8, 0.85);
  rim.position.set(-0.6, 0.3, -2.2);
  scene.add(rim);

  // 正面补光：位置跟着相机走。没有它，朝向观众的那一面永远是死黑——
  // 而那一面恰好是观众唯一在看的面。强度必须低（0.35），
  // 高了就把体积压平，变成一张贴图。
  const front = new THREE.DirectionalLight(0xcfd8e6, 0.35);
  scene.add(front);

  // ── 构件 ──
  const world = new THREE.Group();
  scene.add(world);

  const built = new Map();
  const clipPlane = new THREE.Plane(CLIP_AXIS, 10);
  const allMats = [];

  IR.parts.forEach((part) => {
    const rec = buildPart(part, world);
    rec.part = part;
    rec.visible = true;
    built.set(part.uid, rec);
    allMats.push(rec.mat);
  });

  // ── 包围盒定相机与地面 ──
  world.updateMatrixWorld(true);
  const bbox = new THREE.Box3().setFromObject(world);
  const size = bbox.getSize(new THREE.Vector3());
  const center = bbox.getCenter(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z);

  // 地面就是接触阴影那张平面本身：底板 + 影子一次画完。
  // 分开画（地面一份、影子一份）要处理透明排序，而两片共面的透明面
  // 排序一错，影子就会时有时无——合并成一个 shader 是这个问题的唯一解。
  const contact = makeContactShadow(world, bbox, renderer, { blur: 0.062, shadow: 0.86 });
  const ground = contact.mesh;
  scene.add(ground);
  contact.render();

  const gridR = maxDim * 1.35;
  const grid = new THREE.PolarGridHelper(gridR, 8, 5, 64, 0x2a2622, 0x201d1a);
  grid.position.y = ground.position.y + 0.0006;
  grid.material.transparent = true;
  grid.material.opacity = 0.3;
  scene.add(grid);

  // 轴心线：一条贯穿的虚线。同轴是装配的第一约束，它该被看见，而不是被声称。
  const axisLine = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(bbox.min.x - maxDim * 0.12, center.y, center.z),
      new THREE.Vector3(bbox.max.x + maxDim * 0.12, center.y, center.z),
    ]),
    new THREE.LineDashedMaterial({
      color: 0x7a6444, dashSize: maxDim * 0.018, gapSize: maxDim * 0.014,
      transparent: true, opacity: 0.55,
    }),
  );
  axisLine.computeLineDistances();
  scene.add(axisLine);

  // ── 尺寸线：把每个数字钉回它量过的那一段 ──
  // 工程图上的尺寸线说的是一句很具体的话：「我量了这一段」。
  // 把它画在模型上，「这个数有依据」才从一句声明变成可以指认的东西。
  const dimGroup = new THREE.Group();
  scene.add(dimGroup);
  const dims = [];
  // 标注文字用屏幕空间尺寸：工程标注的大小不该随推拉镜头变化，
  // 否则一放大就变成压住模型的巨字。
  const TAG_W = 0.082;
  const TAG_H = TAG_W / 3.81;
  const DIM_HEX = { measured: 0x9ccf86, inferred: 0xd9a24a, standard: 0x99a0a8 };

  function makeTag(text, grade) {
    const cv = document.createElement('canvas');
    cv.width = 320;
    cv.height = 84;
    const g = cv.getContext('2d');
    g.font = '600 36px ui-monospace, SFMono-Regular, Menlo, monospace';
    g.textAlign = 'center';
    g.textBaseline = 'middle';
    g.fillStyle = '#' + DIM_HEX[grade].toString(16).padStart(6, '0');
    g.fillText(text, 160, 44);
    const tex = new THREE.CanvasTexture(cv);
    tex.minFilter = THREE.LinearFilter;
    tex.anisotropy = 4;
    const sp = new THREE.Sprite(new THREE.SpriteMaterial({
      map: tex, transparent: true, depthTest: false, depthWrite: false,
      opacity: 0.62, sizeAttenuation: false,
    }));
    sp.scale.set(TAG_W, TAG_H, 1);
    sp.renderOrder = 20;
    return sp;
  }

  function seg(points, color, opacity) {
    const g = new THREE.BufferGeometry().setFromPoints(points);
    const m = new THREE.LineBasicMaterial({ color, transparent: true, opacity, depthWrite: false });
    m.userData.base = opacity;        // 记住基准，亮度切换时按比例缩放而不是覆盖
    m.userData.baseColor = color;     // 选中时要换色，同样得记住原色
    return new THREE.Line(g, m);
  }

  (function buildDims() {
    // 两遍：先收集，再按「朝向」分桶统一布局。
    // 一遍布局的问题是每个零件各自外推，结果同一侧的标注高低不齐、互相压住 ——
    // 工程图的读法依赖「同一方向的东西排成一列」，这是排版问题，不是画线问题。
    const specs = [];
    const seenVal = new Set();   // 同一数值只标一次：重复标注会让人去找不存在差异

    IR.parts.forEach((p) => {
      const pbb = new THREE.Box3().setFromObject(built.get(p.uid).holder);
      Object.entries(p.evidence || {}).forEach(([key, ev]) => {
        const an = ev.anchor;
        if (!an) return;
        const vkey = (Math.round(ev.value * 100) / 100).toFixed(2);
        if (seenVal.has(vkey)) return;
        seenVal.add(vkey);

        const a = new THREE.Vector3(...an.a).multiplyScalar(MM);
        const b = new THREE.Vector3(...an.b).multiplyScalar(MM);
        const dir = b.clone().sub(a);
        if (dir.lengthSq() < 1e-10) return;
        dir.normalize();

        // 偏移方向：与尺寸方向垂直、且尽量朝上。
        // 竖直尺寸（直径、厚度）不能往竖直方向再推，改用**侧向**——
        // 而且必须往零件所在的那一侧推。第一版推到 +Z（朝观众），
        // 透视下投影正好糊在模型身上，26 条标注变成一片压在零件上的数字。
        const up = new THREE.Vector3(0, 1, 0);
        if (Math.abs(dir.dot(up)) > 0.85) {
          const px = pbb.getCenter(new THREE.Vector3()).x;
          const ax = bbox.getCenter(new THREE.Vector3()).x;
          up.set(px >= ax ? 1 : -1, 0, 0);
        }
        const off = up.clone().addScaledVector(dir, -up.dot(dir)).normalize();

        // 外推距离必须算到**整个装配体**之外，不是到零件之外。
        // 用零件包围盒算的第一版，凡是跨零件的尺寸（总长、中心距）全部压在模型上——
        // 因为「底座自己很扁」不等于「这条从底座量到电机尾部的尺寸很扁」。
        const edgeDist = (pt) => {
          let t = Infinity;
          ['x', 'y', 'z'].forEach((ax) => {
            const o = off[ax];
            if (Math.abs(o) < 1e-6) return;
            const bound = o > 0 ? bbox.max[ax] : bbox.min[ax];
            t = Math.min(t, (bound - pt[ax]) / o);
          });
          return Number.isFinite(t) ? Math.max(t, 0) : 0;
        };
        const reach = Math.max(edgeDist(a), edgeDist(b));
        specs.push({ p, key, ev, a, b, dir, off, reach });
      });
    });

    const buckets = new Map();
    const dk = (v) => `${Math.round(v.x * 2)},${Math.round(v.y * 2)},${Math.round(v.z * 2)}`;
    specs.forEach((sp) => {
      const k = dk(sp.off);
      if (!buckets.has(k)) buckets.set(k, []);
      buckets.get(k).push(sp);
    });

    const UP = new THREE.Vector3(0, 1, 0);
    buckets.forEach((arr) => {
      const maxReach = Math.max(...arr.map((sp) => sp.reach));

      // 层号必须按**沿桶切向的位置**分配，不能按遍历顺序。
      // 按顺序分层的后果：左边那条被推到最外层、右边那条留在内层，
      // 引出线互相穿越，读起来是一团乱麻。排序之后层次沿切向单调，
      // 「同一排的东西排成一道斜阶梯」——这正是工程图的读法。
      const tangent = new THREE.Vector3().crossVectors(UP, arr[0].off);
      if (tangent.lengthSq() < 1e-8) tangent.set(1, 0, 0);
      tangent.normalize();
      arr.sort((s1, s2) => {
        const m1 = s1.a.clone().add(s1.b).multiplyScalar(0.5).dot(tangent);
        const m2 = s2.a.clone().add(s2.b).multiplyScalar(0.5).dot(tangent);
        return m1 - m2 || s1.ev.value - s2.ev.value;
      });

      // 层距自适应：条数多时收窄，否则最外一条会被推到画面之外。
      // 0.038 是「一眼能分开」的最小值，不再往下压。
      const step = Math.max(0.024, Math.min(0.040, 0.26 / Math.max(arr.length, 1)));
      arr.forEach((sp, i) => {
        drawDim(sp, maxReach + maxDim * (0.028 + step * i));
      });
    });

    function drawDim(sp, gap) {
      const { p, key, ev, a, b, dir, off } = sp;
      const a2 = a.clone().addScaledVector(off, gap);
      const b2 = b.clone().addScaledVector(off, gap);
      const color = DIM_HEX[ev.grade] || DIM_HEX.standard;
      const tint = ev.grade === 'inferred' ? 0.30 : 0.42;

      const g = new THREE.Group();
      g.userData = { uid: p.uid, key, ev };
      g.add(seg([a, a2], color, tint * 0.55));     // 引出线
      g.add(seg([b, b2], color, tint * 0.55));
      g.add(seg([a2, b2], color, tint));           // 尺寸线

      const perp = new THREE.Vector3().crossVectors(dir, off).normalize();
      const tip = maxDim * 0.022;
      [a2, b2].forEach((pt, i) => {
        const sgn = i === 0 ? 1 : -1;
        const back = pt.clone().addScaledVector(dir, tip * sgn);
        g.add(seg([pt, back.clone().addScaledVector(perp, tip * 0.34)], color, tint));
        g.add(seg([pt, back.clone().addScaledVector(perp, -tip * 0.34)], color, tint));
      });

      const sym = (sp.ev.anchor.kind === 'diameter' || sp.ev.anchor.kind === 'hole'
        || sp.ev.anchor.kind === 'pitch') ? '⌀' : '';
      const tag = makeTag(sym + (Math.round(ev.value * 100) / 100), ev.grade);
      tag.position.copy(a2).lerp(b2, 0.5).addScaledVector(off, maxDim * 0.020);
      g.add(tag);

      dimGroup.add(g);
      dims.push({ uid: p.uid, key, group: g, tag, value: ev.value, grade: ev.grade });
    }
  })();

  function setDimsVisible(on) {
    dimGroup.visible = on;
  }

  let activeDim = -1;

  // 标注的亮度只有一个真相：选中的最亮，其次是鼠标指着的那个件的，其余退成背景。
  // 26 条尺寸同时全亮会盖住模型；全暗又等于没做。分层才是工程图的读法。
  function applyDimAlphas() {
    const hov = state.hover;
    dims.forEach((d, i) => {
      let k;
      if (activeDim >= 0) k = i === activeDim ? 1 : 0.07;
      else if (hov) k = d.uid === hov ? 1 : 0.10;
      else k = 0.52;
      const f = k === 1 ? 2.4 : (k < 0.2 ? 0.14 : 0.62);
      d.group.traverse((o) => {
        if (!o.isLine) return;
        o.material.opacity = Math.min(1, (o.material.userData.base || 0.42) * f);
        // 选中时整条线转暖白：1px 的细线在深色底上，只调不透明度是不够的，
        // 必须换色才「跳」出来 —— 这是截图里才看得出来的一件事。
        o.material.color.setHex(k === 1 ? 0xffe4b8 : (o.material.userData.baseColor || 0x999999));
      });
      d.tag.material.opacity = k === 1 ? 1 : (k < 0.2 ? 0.08 : 0.5);
      const sc = k === 1 ? 1.18 : 1;
      d.tag.scale.set(TAG_W * sc, TAG_H * sc, 1);
    });
  }

  function highlightDim(idx) {
    activeDim = idx;
    applyDimAlphas();
  }

  // ── 相机与控制器 ──
  // 按方向算取景距离：包围球法对长条形物体太保守，正视时会把模型缩成一小截。
  // 正确做法是把 8 个角投到相机平面上取最大半宽，再除以 tan(fov/2)。
  function fitDist(dir) {
    const vFov = (camera.fov * Math.PI) / 180;
    const tanV = Math.tan(vFov / 2);
    const tanH = tanV * camera.aspect;
    const forward = dir.clone().normalize().negate();
    const right = new THREE.Vector3().crossVectors(forward, new THREE.Vector3(0, 1, 0));
    if (right.lengthSq() < 1e-6) right.set(1, 0, 0);
    right.normalize();
    const up = new THREE.Vector3().crossVectors(right, forward).normalize();
    let need = 0;
    for (let i = 0; i < 8; i++) {
      const c = new THREE.Vector3(
        i & 1 ? bbox.max.x : bbox.min.x,
        i & 2 ? bbox.max.y : bbox.min.y,
        i & 4 ? bbox.max.z : bbox.min.z,
      ).sub(center);
      // 透视修正：靠近相机的角点投影更大，必须按「深度」单独求距离，
      // 否则正视时前端那圈角一定被切掉一截。
      const depth = c.dot(forward);
      // 目标点已经为右侧面板右移过了，所以左右两侧的可用半宽不再相等：
      // 左边只剩 (1−k)，右边有 (1+k)。不分开算，模型左侧必然被切。
      const k = panelRatio();
      const cr = c.dot(right);
      const needH = cr >= 0 ? cr / (tanH * (1 + k)) : -cr / (tanH * (1 - k));
      need = Math.max(need, Math.abs(c.dot(up)) / tanV - depth, needH - depth);
    }
    // 1.06 而不是 1.0：尺寸线画在零件外侧，取景若只按模型算，
    // 最外圈的数字必然被切掉一半。留白是给标注的，不是给模型的。
    return need * 1.20;
  }

  // 右侧明细面板会吃掉 340px。正确做法不是平移取景框（那会把左边推出画面），
  // 而是把「看的目标点」沿屏幕右方向挪一点 —— 视野保持对称，模型自然落在左侧三分之二。
  function panelRatio() {
    const w = window.innerWidth;
    return w > 900 ? Math.min(340, w * 0.34) / w : 0;
  }

  function frameFor(dir) {
    const v = dir.clone().normalize();
    const d = fitDist(v);
    const fwd = v.clone().negate();
    const right = new THREE.Vector3().crossVectors(fwd, new THREE.Vector3(0, 1, 0));
    if (right.lengthSq() < 1e-6) right.set(1, 0, 0);
    right.normalize();
    const tanH = Math.tan((camera.fov * Math.PI) / 360) * camera.aspect;
    const target = center.clone().addScaledVector(right, d * tanH * panelRatio());
    return { target, pos: target.clone().addScaledVector(v, d) };
  }

  const dirIso = new THREE.Vector3(0.62, 0.52, 0.78);
  const dist = fitDist(dirIso);
  const start = frameFor(dirIso);
  camera.position.copy(start.pos);

  const controls = new OrbitControls(camera, ui.canvas);
  controls.target.copy(start.target);
  controls.enableDamping = true;
  controls.dampingFactor = 0.075;
  controls.minDistance = maxDim * 0.45;
  controls.maxDistance = maxDim * 6;
  // 极角限位：没有它，用户能把相机转到地面以下，看见的是一个空壳，
  // 而且转过去之后很难自己转回来。上限略小于 π/2，永远停在水平线之上。
  controls.minPolarAngle = 0.16;
  controls.maxPolarAngle = Math.PI * 0.492;
  controls.enablePan = false;
  controls.autoRotate = true;
  controls.autoRotateSpeed = 0.55;
  controls.update();

  const VIEWS = {
    iso:   [0.62, 0.52, 0.78],
    front: [0.0, 0.10, 1.0],
    side:  [1.0, 0.10, 0.0],
    top:   [0.0, 1.0, 0.02],
  };

  function flyTo(kind) {
    const v = new THREE.Vector3(...(VIEWS[kind] || VIEWS.iso));
    // 每个视角单独求距离：正视比等轴需要更远，否则两侧一定被切。
    const frame = frameFor(v);
    const from = camera.position.clone();
    const fromT = controls.target.clone();
    const t0 = performance.now();
    const dur = MOTION.dur(MOTION.fly);
    controls.autoRotate = false;
    function step() {
      const k = Math.min((performance.now() - t0) / dur, 1);
      const e = MOTION.easeOutCubic(k);
      camera.position.lerpVectors(from, frame.pos, e);
      controls.target.lerpVectors(fromT, frame.target, e);
      controls.update();
      if (k < 1) requestAnimationFrame(step);
    }
    step();
  }

  // ── 爆炸 / 剖切 ──
  const state = { explode: 0, section: 0, hover: null };

  let dollyBase = 0;

  function applyExplode(v) {
    // 记录开始爆炸前的距离作为基准：否则每拖一次滑块都会在上一次基础上再乘一次，指数膨胀。
    if (state.explode < 0.001 && v > 0.001) {
      dollyBase = camera.position.distanceTo(controls.target);
    }
    state.explode = v;
    const amp = maxDim * 0.36 * v;
    built.forEach((rec) => {
      const d = rec.holder.userData.explode;
      rec.holder.position.copy(rec.holder.userData.basePos).addScaledVector(d, amp);
    });
    updateDimVisibility();
    tip.classList.remove('on');
    contact.markDirty();
    // 零件散开后整体变宽，相机跟着退一点；不退的话两端一定出画。
    const dir = camera.position.clone().sub(controls.target);
    const want = (dollyBase || dist) * (1 + 0.55 * v);
    camera.position.copy(controls.target).add(dir.setLength(want));
  }

  function applySection(v) {
    state.section = v;
    const on = v > 0.02;
    const y0 = bbox.min.y;
    const y1 = bbox.max.y;
    clipPlane.constant = (y0 + (y1 - y0) * (1 - v)) * -1;

    allMats.forEach((m) => {
      m.clippingPlanes = on ? [clipPlane] : [];
      m.needsUpdate = true;
    });
    built.forEach((rec) => {
      rec.edgeMat.clippingPlanes = on ? [clipPlane] : [];
      rec.edgeMat.needsUpdate = true;
    });
    built.forEach((rec) => {
      rec.holder.visible = on || !rec.part.internal;
    });
    ground.visible = !on;
    // 剖切时地面整体让位，接触阴影跟着走。深度通道是 ShaderMaterial，
    // 不吃 clippingPlanes——留着它会在剖开后给出一团「完整外形」的假影。
    contact.mesh.visible = !on;
    grid.visible = !on;
    axisLine.visible = !on;
    updateDimVisibility();
    tip.classList.remove('on');
  }

  let dimsOn = true;

  function updateDimVisibility() {
    dimGroup.visible = dimsOn && state.explode < 0.02 && state.section < 0.02;
  }

  // 相机飞到某个点：面板里点一条尺寸，视线就该落到那个件上。
  function flyToPoint(pt, d) {
    const v = camera.position.clone().sub(controls.target).normalize();
    const from = camera.position.clone();
    const fromT = controls.target.clone();
    const to = pt.clone().addScaledVector(v, d);
    const t0 = performance.now();
    const dur = MOTION.dur(MOTION.fly);
    controls.autoRotate = false;
    (function step() {
      const k = Math.min((performance.now() - t0) / dur, 1);
      const e = MOTION.easeOutCubic(k);
      camera.position.lerpVectors(from, to, e);
      controls.target.lerpVectors(fromT, pt, e);
      controls.update();
      if (k < 1) requestAnimationFrame(step);
    })();
  }

  function focusEvidence(uid, key) {
    const idx = dims.findIndex((d) => d.uid === uid && d.key === key);
    highlightDim(idx);
    const rec = built.get(uid);
    if (rec) {
      const bb = new THREE.Box3().setFromObject(rec.holder);
      const c = bb.getCenter(new THREE.Vector3());
      const r = bb.getSize(new THREE.Vector3()).length();
      flyToPoint(c, Math.max(r * 2.35, maxDim * 0.8));
    }
  }

  // ── 交互 ──
  const ray = new THREE.Raycaster();
  // 拾取阈值的单位是「世界单位」。这个场景是毫米制、模型只有 0.145 米，
  // 而 Line 的默认阈值是 1 —— 等于整个屏幕都在任一描边的命中范围里，
  // 鼠标放在空白处也会点亮某个零件。三行代码，查了一下午。
  ray.params.Line.threshold = maxDim * 0.008;
  ray.params.Points.threshold = maxDim * 0.008;
  const pointer = new THREE.Vector2();

  function pick(ev) {
    const r = ui.canvas.getBoundingClientRect();
    pointer.x = ((ev.clientX - r.left) / r.width) * 2 - 1;
    pointer.y = -((ev.clientY - r.top) / r.height) * 2 + 1;
    ray.setFromCamera(pointer, camera);
    // 只认实体面。描边是给人看的，不是给鼠标点的。
    const hits = ray.intersectObjects(world.children, true);
    for (const h of hits) {
      if (!h.object.isMesh) continue;
      const uid = h.object.userData.partUid;
      if (uid) return uid;
    }
    return null;
  }

  function setHover(uid) {
    if (state.hover === uid) return;
    state.hover = uid;
    built.forEach((rec, id) => {
      const on = id === uid;
      rec.edgeMat.opacity = on ? 0.95 : 0.18;
      rec.edgeMat.color.setHex(on ? 0xe8c48a : EVIDENCE_COLOR[worstGrade(rec.part.evidence)]);
      // 自发光强度要跟着环境亮度走：环境一调亮，0.22 的自发光就被淹没了，
      // 表现为「点了列表，看不出选中了哪个件」。选中必须比环境高一个档才读得出来。
      rec.mat.emissiveIntensity = on ? 0.55 : 0;
      rec.mat.emissive.setHex(on ? 0x6b4f28 : 0x000000);
    });
    document.querySelectorAll('.sv-row').forEach((r) => {
      r.classList.toggle('on', r.dataset.uid === uid);
    });
    if (uid) {
      const row = document.querySelector(`.sv-row[data-uid="${uid}"]`);
      if (row) row.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
    applyDimAlphas();
  }

  // 画布上的即时反馈：鼠标停在哪，就报出这是哪个件、成色如何。
  const tip = el('div', 'sv-tip');
  document.body.appendChild(tip);
  const GRADE_CN = { measured: '图上有标注', inferred: '推断', standard: '标准件' };

  ui.canvas.addEventListener('pointermove', (ev) => {
    const uid = pick(ev);
    setHover(uid);
    if (uid) {
      const p = built.get(uid).part;
      const g = worstGrade(p.evidence);
      tip.innerHTML = `<b>${p.label}</b><i class="${g}">${GRADE_CN[g]}</i>`;
      tip.style.transform = `translate(${ev.clientX + 16}px, ${ev.clientY + 14}px)`;
      tip.classList.add('on');
    } else {
      tip.classList.remove('on');
    }
  });
  ui.canvas.addEventListener('pointerleave', () => { setHover(null); tip.classList.remove('on'); });

  ui.list.addEventListener('click', (ev) => {
    const row = ev.target.closest('.sv-row');
    if (!row) return;
    const uid = row.dataset.uid;
    setHover(uid);
    ui.list.querySelectorAll('dd').forEach((d) => d.classList.remove('sel'));
    const cell = ev.target.closest('dd[data-ev]');
    const ev0 = cell && built.get(uid) && (built.get(uid).part.evidence || {})[cell.dataset.ev];
    if (cell && ev0 && ev0.anchor) {
      cell.classList.add('sel');
      focusEvidence(uid, cell.dataset.ev);
    } else {
      highlightDim(-1);
      const rec = built.get(uid);
      if (rec) {
        const c = new THREE.Box3().setFromObject(rec.holder).getCenter(new THREE.Vector3());
        flyToPoint(c, maxDim * 0.95);
      }
    }
  });

  ui.dock.querySelectorAll('[data-view]').forEach((b) => {
    b.addEventListener('click', () => {
      ui.dock.querySelectorAll('[data-view]').forEach((x) => x.classList.remove('on'));
      b.classList.add('on');
      flyTo(b.dataset.view);
    });
  });

  const expSlider = ui.dock.querySelector('[data-k="explode"]');
  expSlider.addEventListener('input', () => {
    applyExplode(expSlider.value / 100);
    expSlider.parentElement.querySelector('b').textContent = expSlider.value + '%';
  });

  const secSlider = ui.dock.querySelector('[data-k="section"]');
  secSlider.addEventListener('input', () => {
    applySection(secSlider.value / 100);
    secSlider.parentElement.querySelector('b').textContent =
      secSlider.value < 3 ? '关' : secSlider.value + '%';
  });

  ui.dock.querySelector('[data-act="dims"]').addEventListener('click', (e) => {
    dimsOn = !dimsOn;
    e.currentTarget.classList.toggle('on', dimsOn);
    updateDimVisibility();
  });

  ui.dock.querySelector('[data-act="reset"]').addEventListener('click', () => {
    expSlider.value = 0; applyExplode(0);
    secSlider.value = 0; applySection(0);
    highlightDim(-1);
    ui.list.querySelectorAll('dd').forEach((d) => d.classList.remove('sel'));
    updateDimVisibility();
    flyTo('iso');
  });

  // ── 尺寸 ──
  function resize() {
    const w = window.innerWidth;
    const h = window.innerHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  window.addEventListener('resize', resize);
  resize();
  applyDimAlphas();

  // ── 循环 ──
  // 切到后台就不渲染。rAF 会被浏览器节流，但节流是 1 fps 而不是 0 ——
  // 一个开着就烧电的确认件，在笔记本上是会被关掉的。
  let paused = document.hidden;
  document.addEventListener('visibilitychange', () => { paused = document.hidden; });

  // 帧间隔必须钳制：标签页切回来时，第一帧的 dt 可能是几十秒，
  // 所有按 dt 积分的动画会在那一帧直接跳到终点。0.05 s 是 20 fps 的下限。
  let lastFrame = performance.now();
  let slowFrames = 0;
  let downgraded = false;
  function tick() {
    requestAnimationFrame(tick);
    const now = performance.now();
    let dt = (now - lastFrame) / 1000;
    dt = Math.min(dt, 0.05);          // 钳制：切回标签页时第一帧可能是几十秒
    lastFrame = now;

    // 连续两秒跑不到 25 fps，就把像素比降一档。只降一次——
    // 降级是为了能用，不是为了好看；反复降会把画面越擦越糊。
    if (!downgraded) {
      slowFrames = dt > 0.04 ? slowFrames + 1 : 0;
      if (slowFrames > 120) {
        renderer.setPixelRatio(Math.min(devicePixelRatio, 1.25));
        downgraded = true;
      }
    }
    if (paused) return;
    contact.update();          // 只在脏了之后重渲深度，静态时零开销
    controls.update();
    front.position.copy(camera.position);   // 补光始终站在观众这一侧
    renderer.render(scene, camera);
  }
  tick();

  // 首屏：先摆好，再轻轻转，3 秒后停 —— 让人先看清，再给一点动感。
  // 开了「减少动态效果」就不转：这类设置背后常是前庭敏感，旋转会直接引起不适。
  // 注意是「不转」而不是「转得快一点」——无障碍里把动画调慢是错的，该取消。
  if (!MOTION.reduce) {
    setTimeout(() => { controls.autoRotate = false; }, 3200);
  } else {
    controls.autoRotate = false;
  }

  // ── 键盘 ──
  // 触屏和鼠标都覆盖了，键盘没有。对一个要被人反复核对的页面，
  // 只能靠鼠标点构件，等于把「核对」这件事限定在有鼠标的场景里。
  window.addEventListener('keydown', (ev) => {
    const keys = Array.from(ui.list.querySelectorAll('dd'));
    const cur = keys.findIndex((d) => d.classList.contains('sel'));
    if (ev.key === 'Escape') {
      // Esc 的语义是「回到全局」，不是「什么都不选」——
      // 所以除了清选中，要把视角也带回去，否则用户会被留在某个零件跟前。
      highlightDim(-1);
      ui.list.querySelectorAll('dd').forEach((d) => d.classList.remove('sel'));
      ui.list.querySelectorAll('.sv-row').forEach((r) => r.classList.remove('on'));
      setHover(null);
      updateDimVisibility();
      tip.classList.remove('on');
      flyTo('iso');
      return;
    }
    if (ev.key === 'ArrowDown' || ev.key === 'ArrowRight') {
      if (!keys.length) return;
      ev.preventDefault();
      const next = keys[(cur + 1 + keys.length) % keys.length];
      next.click();
      next.scrollIntoView({ block: 'nearest' });
    }
    if (ev.key === 'ArrowUp' || ev.key === 'ArrowLeft') {
      if (!keys.length) return;
      ev.preventDefault();
      const prev = keys[(cur - 1 + keys.length) % keys.length];
      prev.click();
      prev.scrollIntoView({ block: 'nearest' });
    }
  });

  window.__spec = { scene, camera, renderer, controls, built, applyExplode, applySection, flyTo, bbox, center, size, maxDim, fitDist, THREE, dims, dimGroup, focusEvidence, highlightDim };
}

boot(window.__IR);
