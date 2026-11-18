# R3F 工程骨架

React 19 + @react-three/fiber 9.x + three 0.187.x。

```bash
npm install
npm run dev      # 开发
npm run build    # 产出 dist/，可静态托管
```

## 已经做对的几件事

- `dpr={[1, 2]}` 像素比封顶
- `useFrame` 用 `delta` 且钳制 0.05，不 setState、不 new
- 材质用 `useMemo` 统一创建，避免每帧重建
- `OrbitControls` 全参数限位
- `Environment preset="studio"` 提供 IBL，金属才不是黑的

## 接入自己的模型

```jsx
import { useLoader } from '@react-three/fiber';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

function Model() {
  const gltf = useLoader(GLTFLoader, '/model.glb');
  return <primitive object={gltf.scene} />;
}
// 用 <Suspense fallback={null}> 包住，否则整个 Canvas 白屏
```

## 更多

见 Skill 内 `references/16-r3f-track.md`：陷阱清单、性能预算、资源生命周期。
