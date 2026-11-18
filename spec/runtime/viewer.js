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
        <dt>${k}</dt>
        <dd class="${v.grade}">${v.value}<small>${v.src || ''}</small></dd>
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
    <div class="sv-actions"><button class="sv-ghost" data-act="reset">复位</button></div>
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
    return need * 0.97;
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
  }

  // ── 交互 ──
  const ray = new THREE.Raycaster();
  const pointer = new THREE.Vector2();

  function pick(ev) {
    const r = ui.canvas.getBoundingClientRect();
    pointer.x = ((ev.clientX - r.left) / r.width) * 2 - 1;
    pointer.y = -((ev.clientY - r.top) / r.height) * 2 + 1;
    ray.setFromCamera(pointer, camera);
    const hits = ray.intersectObjects(world.children, true);
    for (const h of hits) {
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
    setHover(row.dataset.uid);
    const rec = built.get(row.dataset.uid);
    if (rec) {
      const b = new THREE.Box3().setFromObject(rec.holder).getCenter(new THREE.Vector3());
      controls.target.copy(b);
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

  ui.dock.querySelector('[data-act="reset"]').addEventListener('click', () => {
    expSlider.value = 0; applyExplode(0);
    secSlider.value = 0; applySection(0);
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

  // ── 循环 ──
  function tick() {
    controls.update();
    renderer.render(scene, camera);
    requestAnimationFrame(tick);
  }
  tick();

  // 首屏：先摆好，再轻轻转，3 秒后停 —— 让人先看清，再给一点动感
  setTimeout(() => { controls.autoRotate = false; }, 3200);

  window.__spec = { scene, camera, renderer, controls, built, applyExplode, applySection, flyTo, bbox, center, size, maxDim, fitDist, THREE };
}

boot(window.__IR);
