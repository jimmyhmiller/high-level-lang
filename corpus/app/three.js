import { Vector3, Matrix4, Quaternion, Color, Box3, Euler, MathUtils } from "three";
const v = new Vector3(1, 2, 3).applyMatrix4(new Matrix4().makeRotationX(Math.PI / 2));
console.log(v.toArray().map((x) => x.toFixed(4)).join());
console.log(new Quaternion().setFromEuler(new Euler(0.1, 0.2, 0.3)).toArray().map((x) => x.toFixed(4)).join());
console.log(new Color(0xff8040).getHexString(), MathUtils.clamp(5, 0, 1));
console.log(new Box3().setFromPoints([new Vector3(0, 0, 0), new Vector3(1, 2, 3)]).getSize(new Vector3()).toArray().join());
