export class Counter {
  constructor() {
    this.n = 0;
  }
  inc() {
    this.n += 1;
    return this.n;
  }
  get label() {
    return "counter at " + this.n;
  }
}
export class Twice extends Counter {
  inc() {
    return super.inc() * 2;
  }
}
