import * as THREE from 'three';
export function createFlythrough(camera,controls,{width,depth,relief,onStateChange=()=>{}}) {
  let state='stopped',elapsed=0; const duration=24;
  const curve=new THREE.CatmullRomCurve3([
    new THREE.Vector3(-width*.48,relief+depth*.35,-depth*.48),new THREE.Vector3(-width*.15,relief+depth*.18,-depth*.1),
    new THREE.Vector3(width*.25,relief+depth*.12,depth*.16),new THREE.Vector3(width*.48,relief+depth*.3,depth*.46),
    new THREE.Vector3(0,relief+depth*.48,depth*.1),new THREE.Vector3(-width*.48,relief+depth*.35,-depth*.48)
  ],true,'catmullrom',.35);
  return {
    start(){elapsed=0;state='playing';controls.enabled=false;onStateChange(state)}, pause(){if(state==='playing'){state='paused';onStateChange(state)}}, resume(){if(state==='paused'){state='playing';onStateChange(state)}},
    stop(){state='stopped';controls.enabled=true;onStateChange(state)}, get state(){return state},
    update(dt){if(state!=='playing')return;elapsed=(elapsed+dt)%duration;const t=elapsed/duration,p=curve.getPointAt(t),ahead=curve.getPointAt((t+.012)%1);camera.position.copy(p);camera.lookAt(ahead.x,Math.max(0,ahead.y-relief*.35),ahead.z)}
  };
}
