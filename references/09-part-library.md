# 09 · 构件库

> 不要每次从零建模。这里的每个构件都是可直接抄用的函数：
> 给定参数、返回 `Mesh` 或 `Group`、标注面数量级。
> 组装比雕刻快一个数量级，而且形状可控、可复用、可参数化。

**使用约定**

- 全部使用 `three@0.187.0` 的 API，符号名已核对存在。
- 面数标注为默认参数下的估算值，用于预算判断，不是精确值。
- 所有函数假定 `THREE` 已导入。需要 addon 的会单独注明。
- 尺寸单位统一为**米**（工业/产品场景），建筑场景可整体乘 1000 当毫米用，但同一场景内必须一致。

---

## A · 基础形体

### A1 圆角盒 `roundedBox`

产品外壳、设备机身、包装。直角盒看起来廉价，圆角是"制造感"的第一来源。

```js
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';

function roundedBox(w, h, d, radius = 0.02, seg = 2, mat) {
  const geo = new RoundedBoxGeometry(w, h, d, seg, radius);
  return new THREE.Mesh(geo, mat);
}
```

面数 ≈ `6 * (seg+2)^2 * 2`，seg=2 时约 380。**radius 不超过最短边的 1/4**，否则自交破面。

### A2 胶囊 `capsule`

把手、连接杆、柔性件、角色肢体。

```js
function capsule(r, len, mat, capSeg = 8, radialSeg = 20) {
  const geo = new THREE.CapsuleGeometry(r, len, capSeg, radialSeg);
  return new THREE.Mesh(geo, mat);
}
```

面数 ≈ `radialSeg * (capSeg*2 + 2) * 2`，默认约 720。

### A3 变径管 `taperTube`

沿路径变粗细的管：线束、管道、树枝、血管。

```js
function taperTube(points, radiusFn, tubularSeg = 64, radialSeg = 10, mat) {
  const curve = new THREE.CatmullRomCurve3(points);
  // 用 TubeGeometry 无法逐段变径，改为手工采样构建
  const frames = curve.computeFrenetFrames(tubularSeg, false);
  const positions = [], indices = [];
  for (let i = 0; i <= tubularSeg; i++) {
    const t = i / tubularSeg;
    const p = curve.getPointAt(t);
    const N = frames.normals[i], B = frames.binormals[i];
    const r = radiusFn(t);
    for (let j = 0; j <= radialSeg; j++) {
      const v = (j / radialSeg) * Math.PI * 2;
      const sin = Math.sin(v), cos = -Math.cos(v);
      positions.push(
        p.x + r * (cos * N.x + sin * B.x),
        p.y + r * (cos * N.y + sin * B.y),
        p.z + r * (cos * N.z + sin * B.z)
      );
    }
  }
  for (let i = 1; i <= tubularSeg; i++) {
    for (let j = 1; j <= radialSeg; j++) {
      const a = (radialSeg + 1) * (i - 1) + (j - 1);
      const b = (radialSeg + 1) * i + (j - 1);
      const c = (radialSeg + 1) * i + j;
      const d = (radialSeg + 1) * (i - 1) + j;
      indices.push(a, b, d, b, c, d);
    }
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geo.setIndex(indices);
  geo.computeVertexNormals();
  return new THREE.Mesh(geo, mat);
}
```

面数 = `tubularSeg * radialSeg * 2`，默认 1280。`radiusFn(t)` 可以做成"两端收细"的曲线。

### A4 环形板 `ringPlate`

法兰、垫圈、装饰环、底座。

```js
function ringPlate(rIn, rOut, h, mat, seg = 48) {
  const shape = new THREE.Shape();
  shape.absarc(0, 0, rOut, 0, Math.PI * 2, false);
  const hole = new THREE.Path();
  hole.absarc(0, 0, rIn, 0, Math.PI * 2, true);
  shape.holes.push(hole);
  const geo = new THREE.ExtrudeGeometry(shape, {
    depth: h, bevelEnabled: true, bevelSize: h * 0.08,
    bevelThickness: h * 0.08, bevelSegments: 2, curveSegments: seg,
  });
  geo.rotateX(-Math.PI / 2);
  geo.translate(0, h, 0);
  return new THREE.Mesh(geo, mat);
}
```

面数 ≈ `seg * 8`，默认约 400。

---

## B · 工业件

### B1 六角螺栓 `bolt`

```js
function bolt(r = 0.008, len = 0.04, mat) {
  const g = new THREE.Group();
  const head = new THREE.Mesh(new THREE.CylinderGeometry(r * 1.7, r * 1.7, r * 1.1, 6), mat);
  head.position.y = len / 2 + r * 0.55;
  const shaft = new THREE.Mesh(new THREE.CylinderGeometry(r, r, len, 12), mat);
  g.add(head, shaft);
  return g;
}
```

面数 ≈ 80。做 20 个以上时改用 `InstancedMesh`。

### B2 法兰盘 `flange`

```js
function flange(rIn, rOut, h, holeN, holeR, mat) {
  const shape = new THREE.Shape();
  shape.absarc(0, 0, rOut, 0, Math.PI * 2, false);
  const bore = new THREE.Path();
  bore.absarc(0, 0, rIn, 0, Math.PI * 2, true);
  shape.holes.push(bore);
  const rr = (rIn + rOut) / 2;
  for (let i = 0; i < holeN; i++) {
    const a = (i / holeN) * Math.PI * 2;
    const p = new THREE.Path();
    p.absarc(Math.cos(a) * rr, Math.sin(a) * rr, holeR, 0, Math.PI * 2, true);
    shape.holes.push(p);
  }
  const geo = new THREE.ExtrudeGeometry(shape, {
    depth: h, bevelEnabled: true, bevelSize: h * 0.06, bevelThickness: h * 0.06, bevelSegments: 1,
  });
  geo.rotateX(-Math.PI / 2);
  return new THREE.Mesh(geo, mat);
}
```

面数 ≈ `(48 + holeN * 16) * 4`。**用 Shape.holes 打孔比 CSG 便宜得多**，这是工业件的首选做法。

### B3 直齿轮 `gear`

```js
function gear(rRoot, rTip, teeth, h, mat) {
  const shape = new THREE.Shape();
  const step = (Math.PI * 2) / teeth;
  for (let i = 0; i < teeth; i++) {
    const a = i * step;
    const pts = [
      [rRoot, a], [rTip, a + step * 0.22],
      [rTip, a + step * 0.48], [rRoot, a + step * 0.70],
    ];
    pts.forEach(([r, ang], k) => {
      const x = Math.cos(ang) * r, y = Math.sin(ang) * r;
      if (i === 0 && k === 0) shape.moveTo(x, y); else shape.lineTo(x, y);
    });
  }
  shape.closePath();
  const bore = new THREE.Path();
  bore.absarc(0, 0, rRoot * 0.28, 0, Math.PI * 2, true);
  shape.holes.push(bore);
  const geo = new THREE.ExtrudeGeometry(shape, {
    depth: h, bevelEnabled: true, bevelSize: h * 0.05, bevelThickness: h * 0.05, bevelSegments: 1,
  });
  geo.rotateX(-Math.PI / 2);
  return new THREE.Mesh(geo, mat);
}
```

面数 ≈ `teeth * 8 + 60`，teeth=24 时约 250。齿形是梯形近似，用于可视化足够；真实啮合需要渐开线。

### B4 散热鳍组 `heatSink`

散热器、灯罩、格栅。**必须用实例化**，否则 30 片鳍就是 30 次绘制调用。

```js
function heatSink(w, d, finN, finH, finT, mat) {
  const g = new THREE.Group();
  const base = new THREE.Mesh(new THREE.BoxGeometry(w, finH * 0.12, d), mat);
  g.add(base);
  const finGeo = new THREE.BoxGeometry(w, finH, finT);
  const inst = new THREE.InstancedMesh(finGeo, mat, finN);
  const dummy = new THREE.Object3D();
  const gap = (d - finT) / Math.max(finN - 1, 1);
  for (let i = 0; i < finN; i++) {
    dummy.position.set(0, finH * 0.5 + finH * 0.06, -d / 2 + i * gap);
    dummy.updateMatrix();
    inst.setMatrixAt(i, dummy.matrix);
  }
  inst.instanceMatrix.needsUpdate = true;
  g.add(inst);
  return g;
}
```

面数 = `12 + finN * 12`，finN=18 时 228，但**绘制调用只有 2 次**。

### B5 型材挤出 `extrudeProfile`

工字钢、铝型材、轨道、边框。先画截面，再沿长度挤出。

```js
function extrudeProfile(profilePts, length, mat, bevel = 0) {
  const shape = new THREE.Shape();
  profilePts.forEach(([x, y], i) => (i === 0 ? shape.moveTo(x, y) : shape.lineTo(x, y)));
  shape.closePath();
  const geo = new THREE.ExtrudeGeometry(shape, {
    depth: length, bevelEnabled: bevel > 0,
    bevelSize: bevel, bevelThickness: bevel, bevelSegments: 1,
  });
  geo.center();
  return new THREE.Mesh(geo, mat);
}

// 工字钢截面
const I_BEAM = [[-0.05,0.1],[0.05,0.1],[0.05,0.08],[0.01,0.08],
                [0.01,-0.08],[0.05,-0.08],[0.05,-0.1],[-0.05,-0.1],
                [-0.05,-0.08],[-0.01,-0.08],[-0.01,0.08],[-0.05,0.08]];
```

面数 ≈ `点数 * 6`。这是"用 2D 换 3D"最省的做法。

---

## C · 电子件

### C1 电芯阵列 `cellArray`

电池包、储能柜、电芯模组。

```js
function cellArray(rows, cols, cellR, cellH, gapR, cellMat, holderMat) {
  const g = new THREE.Group();
  const holder = new THREE.Mesh(
    new THREE.BoxGeometry(cols * cellR * 2 + gapR * (cols + 1), cellH * 0.18,
                          rows * cellR * 2 + gapR * (rows + 1)),
    holderMat
  );
  g.add(holder);
  const geo = new THREE.CylinderGeometry(cellR, cellR, cellH, 16);
  const inst = new THREE.InstancedMesh(geo, cellMat, rows * cols);
  const d = new THREE.Object3D();
  let i = 0;
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      d.position.set(
        (c - (cols - 1) / 2) * (cellR * 2 + gapR),
        cellH * 0.09 + cellH / 2,
        (r - (rows - 1) / 2) * (cellR * 2 + gapR)
      );
      d.updateMatrix();
      inst.setMatrixAt(i++, d.matrix);
    }
  }
  inst.instanceMatrix.needsUpdate = true;
  g.add(inst);
  return g;
}
```

6×4 阵列：面数 `64 + 24*96 = 2368`，绘制调用 3 次。

### C2 电路板 `pcb`

```js
function pcb(w, d, t, mat, traceMat) {
  const g = new THREE.Group();
  const board = new THREE.Mesh(new THREE.BoxGeometry(w, t, d), mat);
  g.add(board);
  // 走线：用细长方体模拟，比贴图更有立体感
  const traceGeo = new THREE.BoxGeometry(w * 0.8, t * 0.15, 0.0015);
  for (let i = 0; i < 7; i++) {
    const line = new THREE.Mesh(traceGeo, traceMat);
    line.position.set(0, t * 0.55, -d * 0.35 + i * (d * 0.7 / 6));
    line.scale.x = 0.4 + Math.random() * 0.6;
    g.add(line);
  }
  return g;
}
```

面数 ≈ `12 + 7*12 = 96`。

### C3 线圈绕组 `coilWinding`

电机定子、变压器、电感。

```js
function coilWinding(rMean, turns, wireR, mat, seg = 32) {
  const pts = [];
  for (let i = 0; i <= turns * seg; i++) {
    const t = i / (turns * seg);
    const a = t * Math.PI * 2 * turns;
    pts.push(new THREE.Vector3(
      Math.cos(a) * rMean,
      (t - 0.5) * wireR * 2.4,
      Math.sin(a) * rMean
    ));
  }
  const curve = new THREE.CatmullRomCurve3(pts);
  const geo = new THREE.TubeGeometry(curve, turns * seg, wireR, 6, false);
  return new THREE.Mesh(geo, mat);
}
```

turns=6、seg=32 时面数 ≈ `192 * 6 * 2 = 2304`。**turns 不要超过 12**，面数线性涨。

### C4 连接器 `connector`

```js
function connector(pins, pinR, pitch, mat, shellMat) {
  const g = new THREE.Group();
  const w = pins * pitch + pitch;
  const shell = new THREE.Mesh(new THREE.BoxGeometry(w, pitch * 1.6, pitch * 1.4), shellMat);
  g.add(shell);
  const geo = new THREE.CylinderGeometry(pinR, pinR, pitch * 2.2, 8);
  for (let i = 0; i < pins; i++) {
    const p = new THREE.Mesh(geo, mat);
    p.rotation.x = Math.PI / 2;
    p.position.set((i - (pins - 1) / 2) * pitch, 0, pitch * 1.2);
    g.add(p);
  }
  return g;
}
```

面数 ≈ `12 + pins * 32`。

---

## D · 机械件

### D1 螺旋弹簧 `spring`

悬挂、减震、机构回位。**用 TubeGeometry 沿螺旋线扫掠**，比 Lathe 更真实。

```js
function spring(rCoil, h, turns, wireR, mat) {
  const pts = [];
  const N = turns * 40;
  for (let i = 0; i <= N; i++) {
    const t = i / N;
    const a = t * Math.PI * 2 * turns;
    pts.push(new THREE.Vector3(
      Math.cos(a) * rCoil,
      t * h - h / 2,
      Math.sin(a) * rCoil
    ));
  }
  const curve = new THREE.CatmullRomCurve3(pts);
  const geo = new THREE.TubeGeometry(curve, N, wireR, 6, false);
  return new THREE.Mesh(geo, mat);
}
```

turns=8 时面数 ≈ `320 * 6 * 2 = 3840`。降到 `turns*24` 采样可减半。

### D2 减震器 `damper`

```js
function damper(rOuter, len, mat, shaftMat) {
  const g = new THREE.Group();
  const body = new THREE.Mesh(new THREE.CylinderGeometry(rOuter, rOuter, len * 0.62, 20), mat);
  body.position.y = len * 0.19;
  const shaft = new THREE.Mesh(new THREE.CylinderGeometry(rOuter * 0.34, rOuter * 0.34, len, 12), shaftMat);
  shaft.position.y = -len * 0.1;
  const cap = new THREE.Mesh(new THREE.CylinderGeometry(rOuter * 0.62, rOuter * 0.62, len * 0.1, 20), mat);
  cap.position.y = -len * 0.16;
  g.add(body, shaft, cap);
  return g;
}
```

面数 ≈ 640。

### D3 A 臂 `aArm`

悬挂摆臂。用两个圆柱 + 球头，比布尔运算便宜。

```js
function aArm(root, tipA, tipB, r, mat) {
  const g = new THREE.Group();
  const make = (a, b) => {
    const dir = new THREE.Vector3().subVectors(b, a);
    const len = dir.length();
    const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r * 0.8, len, 10), mat);
    m.position.copy(a).addScaledVector(dir, 0.5);
    m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.normalize());
    return m;
  };
  g.add(make(root, tipA), make(root, tipB));
  const ball = new THREE.Mesh(new THREE.SphereGeometry(r * 1.4, 12, 8), mat);
  ball.position.copy(root);
  g.add(ball);
  return g;
}
```

面数 ≈ 560。

### D4 轮组 `wheel`

轮胎 + 轮辋 + 辐条。

```js
function wheel(r, width, rimR, spokeN, tireMat, rimMat) {
  const g = new THREE.Group();
  const tire = new THREE.Mesh(new THREE.CylinderGeometry(r, r, width, 40, 1, false), tireMat);
  tire.rotation.z = Math.PI / 2;
  g.add(tire);
  // 胎壁圆角，让轮胎不是"圆柱"
  [-1, 1].forEach(s => {
    const side = new THREE.Mesh(new THREE.TorusGeometry(r * 0.94, width * 0.16, 8, 36), tireMat);
    side.rotation.y = Math.PI / 2;
    side.position.x = s * width * 0.42;
    g.add(side);
  });
  const rim = new THREE.Mesh(new THREE.CylinderGeometry(rimR, rimR, width * 0.86, 32, 1, true), rimMat);
  rim.rotation.z = Math.PI / 2;
  g.add(rim);
  const spokeGeo = new THREE.BoxGeometry(width * 0.5, rimR * 1.9, rimR * 0.16);
  for (let i = 0; i < spokeN; i++) {
    const s = new THREE.Mesh(spokeGeo, rimMat);
    s.rotation.x = (i / spokeN) * Math.PI * 2;
    g.add(s);
  }
  return g;
}
```

面数 ≈ `80 + 2*576 + 64 + spokeN*12`，spokeN=10 时约 1420。

### D5 胎面花纹 `tread`

```js
function tread(r, width, lugs, lugH, lugW, mat) {
  const geo = new THREE.BoxGeometry(lugW, lugH, width * 0.9);
  const inst = new THREE.InstancedMesh(geo, mat, lugs);
  const d = new THREE.Object3D();
  for (let i = 0; i < lugs; i++) {
    const a = (i / lugs) * Math.PI * 2;
    d.position.set(Math.cos(a) * (r - lugH * 0.4), Math.sin(a) * (r - lugH * 0.4), 0);
    d.rotation.z = a;
    d.updateMatrix();
    inst.setMatrixAt(i, d.matrix);
  }
  inst.instanceMatrix.needsUpdate = true;
  return inst;
}
```

---

## E · 建筑件

### E1 开洞墙体 `wallWithOpenings`

```js
function wallWithOpenings(w, h, t, openings, mat) {
  const shape = new THREE.Shape();
  shape.moveTo(-w / 2, 0); shape.lineTo(w / 2, 0);
  shape.lineTo(w / 2, h); shape.lineTo(-w / 2, h);
  shape.closePath();
  openings.forEach(o => {
    const p = new THREE.Path();
    p.moveTo(o.x - o.w / 2, o.y);
    p.lineTo(o.x + o.w / 2, o.y);
    p.lineTo(o.x + o.w / 2, o.y + o.h);
    p.lineTo(o.x - o.w / 2, o.y + o.h);
    p.closePath();
    shape.holes.push(p);
  });
  const geo = new THREE.ExtrudeGeometry(shape, { depth: t, bevelEnabled: false });
  return new THREE.Mesh(geo, mat);
}
```

面数 ≈ `(4 + openings*4) * 6`。**不要用 CSG 做墙洞**，慢且易破面。

### E2 楼梯 `staircase`

```js
function staircase(steps, rise, run, width, mat) {
  const g = new THREE.Group();
  const geo = new THREE.BoxGeometry(width, rise, run);
  const inst = new THREE.InstancedMesh(geo, mat, steps);
  const d = new THREE.Object3D();
  for (let i = 0; i < steps; i++) {
    d.position.set(0, rise * (i + 0.5), -i * run);
    d.updateMatrix();
    inst.setMatrixAt(i, d.matrix);
  }
  inst.instanceMatrix.needsUpdate = true;
  g.add(inst);
  return g;
}
```

### E3 幕墙 `curtainWall`

```js
function curtainWall(w, h, cols, rows, frameMat, glassMat) {
  const g = new THREE.Group();
  const cw = w / cols, ch = h / rows;
  const frameGeo = new THREE.BoxGeometry(cw * 0.06, ch, 0.02);
  const frames = new THREE.InstancedMesh(frameGeo, frameMat, cols * (rows + 1));
  const d = new THREE.Object3D();
  let i = 0;
  for (let c = 0; c <= cols; c++) {
    for (let r = 0; r < rows; r++) {
      d.position.set(-w / 2 + c * cw, ch * (r + 0.5), 0);
      d.updateMatrix();
      if (i < cols * (rows + 1)) frames.setMatrixAt(i++, d.matrix);
    }
  }
  frames.instanceMatrix.needsUpdate = true;
  g.add(frames);
  const glass = new THREE.Mesh(new THREE.PlaneGeometry(w, h), glassMat);
  glass.position.y = h / 2;
  g.add(glass);
  return g;
}
```

玻璃用**一整块平面**而不是每格一块，绘制调用从 `cols*rows` 降到 1。

---

## F · 自然件

### F1 地形 `terrain`

```js
function terrain(w, d, seg, heightFn, mat) {
  const geo = new THREE.PlaneGeometry(w, d, seg, seg);
  geo.rotateX(-Math.PI / 2);
  const pos = geo.attributes.position;
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i), z = pos.getZ(i);
    pos.setY(i, heightFn(x, z));
  }
  geo.computeVertexNormals();
  return new THREE.Mesh(geo, mat);
}
// 用法：terrain(20, 20, 96, (x,z) => Math.sin(x*0.3)*Math.cos(z*0.25)*0.6, mat)
```

面数 = `seg^2 * 2`，seg=96 时 18432。

### F2 岩石群 `rockCluster`

```js
function rockCluster(n, seed, size, mat) {
  const rand = (() => { let s = seed; return () => (s = (s * 16807) % 2147483647) / 2147483647; })();
  const g = new THREE.Group();
  for (let i = 0; i < n; i++) {
    const geo = new THREE.IcosahedronGeometry(size * (0.5 + rand()), 1);
    const pos = geo.attributes.position;
    for (let k = 0; k < pos.count; k++) {
      const f = 0.82 + rand() * 0.36;
      pos.setXYZ(k, pos.getX(k) * f, pos.getY(k) * f * 0.8, pos.getZ(k) * f);
    }
    geo.computeVertexNormals();
    const m = new THREE.Mesh(geo, mat);
    m.position.set((rand() - 0.5) * size * 6, rand() * size * 0.4, (rand() - 0.5) * size * 6);
    m.rotation.set(rand() * 6, rand() * 6, rand() * 6);
    g.add(m);
  }
  return g;
}
```

单个 icosahedron detail=1 是 80 面，n=12 时 960 面。**用固定种子的 LCG 保证每次生成一致**。

### F3 水面 `waterSurface`

```js
function waterSurface(w, d, seg, mat, amp = 0.06) {
  const geo = new THREE.PlaneGeometry(w, d, seg, seg);
  geo.rotateX(-Math.PI / 2);
  const base = geo.attributes.position.array.slice();
  const mesh = new THREE.Mesh(geo, mat);
  mesh.userData.update = (t) => {
    const pos = geo.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      const x = base[i * 3], z = base[i * 3 + 2];
      pos.setY(i, Math.sin(x * 1.8 + t * 1.4) * Math.cos(z * 1.5 + t * 1.1) * amp);
    }
    pos.needsUpdate = true;
    geo.computeVertexNormals();
  };
  return mesh;
}
```

**顶点动画每帧重算法线很贵**。seg 超过 64 就改用 shader 或法线贴图。

---

## G · 抽象件

### G1 点云 `pointCloud`

```js
function pointCloud(n, r, seed, color, size = 0.01) {
  const rand = (() => { let s = seed; return () => (s = (s * 16807) % 2147483647) / 2147483647; })();
  const pos = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    const th = rand() * Math.PI * 2, ph = Math.acos(2 * rand() - 1);
    const rr = r * Math.cbrt(rand());
    pos[i * 3] = Math.sin(ph) * Math.cos(th) * rr;
    pos[i * 3 + 1] = Math.cos(ph) * rr;
    pos[i * 3 + 2] = Math.sin(ph) * Math.sin(th) * rr;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  return new THREE.Points(geo, new THREE.PointsMaterial({ color, size, sizeAttenuation: true }));
}
```

**一次绘制调用**，n 可以到 5 万。

### G2 数据柱 `dataBars`

```js
function dataBars(values, maxH, barW, gap, mat, colorFn) {
  const g = new THREE.Group();
  const geo = new THREE.BoxGeometry(barW, 1, barW);
  values.forEach((v, i) => {
    const m = new THREE.Mesh(geo, colorFn ? colorFn(v) : mat);
    m.scale.y = Math.max((v / Math.max(...values)) * maxH, 0.001);
    m.position.set((i - (values.length - 1) / 2) * (barW + gap), m.scale.y / 2, 0);
    g.add(m);
  });
  return g;
}
```

### G3 网格穹顶 `geoDome`

```js
function geoDome(r, detail, mat) {
  const geo = new THREE.IcosahedronGeometry(r, detail);
  const edges = new THREE.WireframeGeometry(geo);
  const line = new THREE.LineSegments(edges, mat);
  return line;
}
```

detail=2 时约 640 段线。做科技感背景比实心球高级得多。

---

## 组合策略

### 构件树，不是零件堆

```
carRoot
├── bodyG      车身外壳（A1 + B5）
├── wheelG×4   wheel() + tread()
├── chassisG   型材骨架（B5）
└── detailG    螺栓/线束/标牌（B1 / A3）
```

每一层用一个 `Group`，只对 Group 做位移/旋转。**不要对几十个 Mesh 逐个设 position**，改一次父级就够。

### 共用几何与材质

```js
// 好：一个几何，多个 Mesh
const boltGeo = new THREE.CylinderGeometry(r, r, len, 12);
const boltMat = new THREE.MeshStandardMaterial({ metalness: 1, roughness: 0.35 });
[0, 1, 2, 3].forEach(i => {
  const b = new THREE.Mesh(boltGeo, boltMat);
  b.position.set(i * 0.05, 0, 0);
  group.add(b);
});
```

几何和材质是显存对象，Mesh 只是"引用 + 变换"。重复创建几何是新手最常见的浪费。

### 什么时候用 InstancedMesh

| 数量 | 做法 |
|---|---|
| 1–5 | 普通 Mesh |
| 6–30 | 普通 Mesh + 共用 geometry/material |
| 30+ 且形状相同 | `InstancedMesh` |
| 30+ 但形状各异 | 合并几何（`BufferGeometryUtils.mergeGeometries`） |

---

## 自检

- [ ] 每个构件都有明确的参数含义和单位
- [ ] 数量 >30 的重复件用了 InstancedMesh
- [ ] 几何/材质有复用，没有在循环里 `new`
- [ ] 打孔用 `Shape.holes` 而不是 CSG
- [ ] 总面数在预算内（中端设备 <200k）
- [ ] 所有 `THREE.X` 都通过了 `api_lookup.py --check`
