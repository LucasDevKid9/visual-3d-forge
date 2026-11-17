import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

/**
 * 场景主体。三条铁律：
 * 1. useFrame 内不 setState —— 直接改 three 对象
 * 2. useFrame 内不 new —— 复用模块级临时对象
 * 3. 所有动画用 delta 并钳制上限
 */
export default function Scene() {
  const group = useRef();

  const materials = useMemo(() => ({
    metal: new THREE.MeshPhysicalMaterial({
      color: '#d8dde2', metalness: 1.0, roughness: 0.18, envMapIntensity: 1.0,
    }),
    dark: new THREE.MeshPhysicalMaterial({
      color: '#12161c', metalness: 0.2, roughness: 0.55,
    }),
    glow: new THREE.MeshStandardMaterial({
      color: '#0a1418', emissive: '#38f2ff', emissiveIntensity: 2.0,
      metalness: 0, roughness: 0.5,
    }),
  }), []);

  useFrame((_, delta) => {
    const dt = Math.min(delta, 0.05);
    if (group.current) group.current.rotation.y += dt * 0.4;
  });

  return (
    <group ref={group}>
      <mesh material={materials.metal} castShadow>
        <torusKnotGeometry args={[0.8, 0.26, 160, 24]} />
      </mesh>

      <mesh position={[0, 0.98, 0]} material={materials.glow}>
        <sphereGeometry args={[0.06, 16, 12]} />
      </mesh>

      <mesh position={[0, -1.1, 0]} material={materials.dark} receiveShadow>
        <cylinderGeometry args={[1.4, 1.5, 0.12, 64]} />
      </mesh>
    </group>
  );
}
