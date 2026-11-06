import { helper, Kind } from "../ts/lib";
export enum Local { A = 1 }
const load = () => import("./ts-dyn");
load().then((m) => console.log(helper(), Kind.K1, Local.A, m.dynValue));
