import { z } from "zod/v4";
export const statuses = ["planned", "active", "done"];
export const Project = z.object({
  id: z.string().min(1), name: z.string().trim().min(2).max(80),
  owner: z.string().trim().min(1).max(60), status: z.enum(statuses),
  budget: z.number().int().min(0).max(10000000), updated: z.string().datetime()
});
export const ProjectInput = Project.omit({ id: true, updated: true });
export const Portfolio = z.array(Project);
export function summarize(projects) {
  return {
    count: projects.length,
    active: projects.filter(p => p.status === "active").length,
    done: projects.filter(p => p.status === "done").length,
    budget: projects.reduce((sum, p) => sum + p.budget, 0)
  };
}
