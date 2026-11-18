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
  cast_iron:      { color: 0x4b4f55, metalness: 0.35, roughness: 0.74 },
  steel:          { color: 0xbabfc7, metalness: 0.96, roughness: 0.24 },
  aluminum:       { color: 0xc9cdd3, metalness: 0.88, roughness: 0.38 },
  brass:          { color: 0xb08d57, metalness: 0.92, roughness: 0.32 },
  anodized_black: { color: 0x343941, metalness: 0.62, roughness: 0.36 },
  rubber:         { color: 0x1a1c1e, metalness: 0.05, roughness: 0.90 },
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

  const mat = new THREE.MeshStandardMaterial({
    ...MATERIALS[part.material] || MATERIALS.steel,
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
    m.castShadow = true;
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

function boot(IR) {
  const ui = buildShell(IR);

  const renderer = new THREE.WebGLRenderer({ canvas: ui.canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.localClippingEnabled = true;

  const scene = new THREE.Scene();
  scene.fog = new THREE.Fog(0x121110, 1.6, 4.2);

  const camera = new THREE.PerspectiveCamera(36, 1, 0.01, 60);

  // 环境反射：用一个小「柔光棚」而不是一张渐变图。
  // 渐变图在横向只有十几个像素，高粗糙度材质采样最低 mip 时会被放大成大色块——
  // 表现为曲面上莫名其妙的马赛克。这是必须用真实几何做环境的原因。
  const pmrem = new THREE.PMREMGenerator(renderer);
  const envScene = new THREE.Scene();
  const roomGeo = new THREE.BoxGeometry(10, 6, 10);
  const roomMat = new THREE.MeshBasicMaterial({ color: 0x14171b, side: THREE.BackSide });
  envScene.add(new THREE.Mesh(roomGeo, roomMat));

  const soft = new THREE.MeshBasicMaterial({ color: 0xffffff });
  const panels = [
    [3.2, 0.012, 3.2, [0, 2.9, 0], 1.5],       // 顶灯
    [0.012, 2.0, 3.0, [-4.8, 0.4, 0], 1.1],    // 左侧条光
    [0.012, 1.6, 2.4, [4.8, 0.2, 1.2], 0.85],  // 右侧条光
    [2.4, 1.2, 0.012, [0, 0.3, -4.8], 0.5],    // 背后轮廓
  ];
  panels.forEach(([w, h, d, pos, k]) => {
    const m = new THREE.Mesh(
      new THREE.BoxGeometry(w, h, d),
      new THREE.MeshBasicMaterial({ color: new THREE.Color(k, k, k * 1.06) }),
    );
    m.position.set(...pos);
    envScene.add(m);
  });

  const envRT = pmrem.fromScene(envScene, 0.04);
  const env = envRT.texture;
  scene.environment = env;
  scene.environmentIntensity = 0.95;

  // 三光：主光有阴影，补光冷，轮廓光从背后切边
  scene.add(new THREE.HemisphereLight(0x9fb0c8, 0x231d18, 0.72));

  const key = new THREE.DirectionalLight(0xfff2e0, 1.95);
  key.position.set(1.8, 2.4, 1.5);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  key.shadow.camera.near = 0.1;
  key.shadow.camera.far = 8;
  key.shadow.camera.left = -1.2;
  key.shadow.camera.right = 1.2;
  key.shadow.camera.top = 1.2;
  key.shadow.camera.bottom = -1.2;
  key.shadow.bias = -0.0004;
  key.shadow.normalBias = 0.04;
  scene.add(key);

  const fill = new THREE.DirectionalLight(0x9aabc4, 0.48);
  fill.position.set(-1.6, 0.9, -1.2);
  scene.add(fill);

  const rim = new THREE.DirectionalLight(0xffd9a8, 0.85);
  rim.position.set(-0.6, 0.3, -2.2);
  scene.add(rim);

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

  const ground = new THREE.Mesh(
    new THREE.CircleGeometry(maxDim * 2.4, 64),
    new THREE.ShadowMaterial({ opacity: 0.42 }),
  );
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = bbox.min.y - 0.001;
  ground.receiveShadow = true;
  scene.add(ground);

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
    m.userData.base = opacity;   // 记住基准，亮度切换时按比例缩放而不是覆盖
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
      const ph = pbb.getSize(new THREE.Vector3()).multiplyScalar(0.5);
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

        // 偏移方向：与尺寸方向垂直、且尽量朝上
        const up = new THREE.Vector3(0, 1, 0);
        if (Math.abs(dir.dot(up)) > 0.85) up.set(0, 0, 1);
        const off = up.clone().addScaledVector(dir, -up.dot(dir)).normalize();

        // 越过这个零件在该方向上的轮廓，否则标注压在模型上
        const reach = Math.abs(ph.x * off.x) + Math.abs(ph.y * off.y) + Math.abs(ph.z * off.z);
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

    buckets.forEach((arr) => {
      const maxReach = Math.max(...arr.map((sp) => sp.reach));
      arr.forEach((sp, i) => {
        drawDim(sp, maxReach + maxDim * (0.028 + 0.038 * i));
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
        if (o.isLine) o.material.opacity = Math.min(1, (o.material.userData.base || 0.42) * f);
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
    return need * 1.06;
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
    const dur = 620;
    controls.autoRotate = false;
    function step() {
      const k = Math.min((performance.now() - t0) / dur, 1);
      const e = 1 - Math.pow(1 - k, 3);
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
    controls.autoRotate = false;
    (function step() {
      const k = Math.min((performance.now() - t0) / 620, 1);
      const e = 1 - Math.pow(1 - k, 3);
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
      rec.mat.emissiveIntensity = on ? 0.22 : 0;
      rec.mat.emissive.setHex(on ? 0x3a2f1e : 0x000000);
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
  function tick() {
    controls.update();
    renderer.render(scene, camera);
    requestAnimationFrame(tick);
  }
  tick();

  // 首屏：先摆好，再轻轻转，3 秒后停 —— 让人先看清，再给一点动感
  setTimeout(() => { controls.autoRotate = false; }, 3200);

  window.__spec = { scene, camera, renderer, controls, built, applyExplode, applySection, flyTo, bbox, center, size, maxDim, fitDist, THREE, dims, dimGroup, focusEvidence, highlightDim };
}

boot(window.__IR);
