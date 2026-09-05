import * as THREE from 'three';
export function createCamera(width,depth,relief,{minimumEyeHeight=1.7}={}) {
  const span=Math.max(width,depth,1),eyeHeight=Math.max(minimumEyeHeight,span*.018,relief*.035);
  const camera=new THREE.PerspectiveCamera(58,1,Math.max(.05,span/10000),span*30+relief*10+100);
  const home=new THREE.Vector3(0,eyeHeight,-depth*.44);
  const target=new THREE.Vector3(0,eyeHeight,-depth*.2);
  camera.position.copy(home);camera.lookAt(target);camera.rotation.order='YXZ';
  return {camera,home,target,eyeHeight,moveSpeed:Math.max(span*.16,1)};
}
