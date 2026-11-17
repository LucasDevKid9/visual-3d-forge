# vendor · three.js 0.187.0

由 `scripts/vendor.py` 生成，**不要手工编辑**。重新生成：

```bash
python3 scripts/vendor.py --three <three包根> --out assets/vendor --profile standard
```

- 文件数：18
- 总体积：2391.0 KB
- addon：controls/MapControls.js, controls/OrbitControls.js, controls/TrackballControls.js, environments/RoomEnvironment.js, lines/Line2.js, lines/LineGeometry.js, lines/LineMaterial.js, lines/LineSegments2.js, lines/LineSegmentsGeometry.js, loaders/GLTFLoader.js, loaders/HDRLoader.js, loaders/RGBELoader.js, renderers/CSS2DRenderer.js, renderers/CSS3DRenderer.js, utils/BufferGeometryUtils.js, utils/SkeletonUtils.js

## 用法 A · 本地工程（D2）

目录结构保持 `vendor/` 与 HTML 同级，importmap 指向相对路径：

```html
<script type="importmap">
{
  "imports": {
    "three": "./vendor/three.module.js",
    "three/addons/": "./vendor/addons/"
  }
}
</script>
```

## 用法 B · 单文件离线（D1）

```bash
python3 scripts/bundle.py --src scene.html --vendor vendor --out scene.offline.html
```

bundle.py 会把每个模块转成 `data:text/javascript;base64,...` 写回 importmap，
产出的 HTML 不再需要任何外部文件，可直接双击、邮件附件、内网分发。

## 注意

- `three.module.js` 从 `three.core.js` re-export，两者必须同目录，不可拆分。
- 以下模块需额外部署解码器：{}
