// The app's data: seeded deterministically, validated by schemas, as an API response would be.
import { z } from "zod";

export const Tag = z.enum(["ui", "api", "infra", "docs", "research"]);
export const Task = z.object({
  id: z.string().regex(/^t\d+$/),
  title: z.string().min(3).max(80),
  estimate: z.number().int().positive().max(40),
  done: z.boolean(),
  due: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  tags: z.array(Tag).min(1),
  assignee: z.string().nullable(),
});
export const Project = z.object({
  id: z.string(),
  name: z.string().min(2),
  owner: z.string().email(),
  budget: z.number().nonnegative(),
  tasks: z.array(Task),
});
export const Projects = z.array(Project);

const people = ["ada", "grace", "edsger", "barbara", "alan", "margaret", "ken", "frances"];
const words = ["parser", "cache", "index", "layout", "router", "schema", "billing", "search", "export", "audit"];
const tags = Tag.options;

function pad(n) { return String(n).padStart(2, "0"); }

export function seed(projectCount = 24, tasksPer = 18) {
  return Array.from({ length: projectCount }, (_, p) => ({
    id: "p" + p,
    name: words[p % words.length] + " " + (p + 1),
    owner: people[p % people.length] + "@example.com",
    budget: ((p * 7919) % 50000) + 1000,
    tasks: Array.from({ length: tasksPer }, (_, t) => {
      const n = p * tasksPer + t;
      return {
        id: "t" + n,
        title: "Make the " + words[(n * 3) % words.length] + " " + ["faster", "smaller", "correct", "simpler"][n % 4],
        estimate: (n % 13) + 1,
        done: n % 3 === 0,
        due: "2024-" + pad((n % 12) + 1) + "-" + pad((n % 27) + 1),
        tags: [tags[n % tags.length], tags[(n * 7) % tags.length]].filter((x, i, xs) => xs.indexOf(x) === i),
        assignee: n % 5 === 0 ? null : people[n % people.length],
      };
    }),
  }));
}

export const projects = Projects.parse(seed());
