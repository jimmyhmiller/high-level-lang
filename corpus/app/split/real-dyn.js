import { max, min, extent } from "d3";
import { sortBy } from "lodash-es";
export const summary = (xs) => JSON.stringify([max(xs), min(xs), extent(xs), sortBy(xs)]);
export default "dyn";
