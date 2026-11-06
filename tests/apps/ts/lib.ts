export class Base { v = 1; }
export const helper = () => "helped";
export type OnlyType = number;
export interface Iface { x: 1 }
export enum Kind { K1 = "k", K2 = 2 }
export const UnusedValue = 1;
export const named = "named";
export default 42;
export { Iface as ReexportedType };
