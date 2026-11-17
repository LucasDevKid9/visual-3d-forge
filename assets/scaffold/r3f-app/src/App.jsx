import { Canvas } from '@react-three/fiber';
import { Environment, OrbitControls } from '@react-three/drei';
import * as THREE from 'three';
import Scene from './Scene.jsx';

export default function App() {
  return (
    <Canvas
      dpr={[1, 2]}
      shadows
      camera={{ position: [3.2, 2.4, 4.2], fov: 38 }}
      gl={{ antialias: true, toneMapping: THREE.ACESFilmicToneMapping }}
    >
      <color attach="background" args={['#070d14']} />
      <fog attach="fog" args={['#070d14', 9, 24]} />

      <Environment preset="studio" />
      <ambientLight intensity={0.35} />
      <directionalLight
        position={[4, 6, 3]}
        intensity={2.2}
        castShadow
        shadow-mapSize={[1024, 1024]}
      />
      <directionalLight position={[-4, 2, -3]} intensity={0.9} color="#38f2ff" />

      <Scene />

      <OrbitControls
        enablePan={false}
        minDistance={3}
        maxDistance={9}
        minPolarAngle={Math.PI * 0.18}
        maxPolarAngle={Math.PI * 0.48}
      />
    </Canvas>
  );
}
