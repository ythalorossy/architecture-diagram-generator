// OpenCode plugin entry point. It only registers the skills/ folder, so
// OpenCode's native `skill` tool can load the skill. Nothing else runs.
//
// opencode.json:  "plugin":  ["architecture-diagram-generator@git+https://github.com/ythalorossy/architecture-diagram-generator.git"]   (V1)
//                 "plugins": [same]                                                                                                  (V2, 2.0.4+)
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const skillsDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "skills");

function parseFrontmatter(text) {
  const match = text.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?/);
  if (!match) return { frontmatter: {}, content: text };
  const frontmatter = {};
  for (const line of match[1].split(/\r?\n/)) {
    const field = line.match(/^([\w-]+):\s*(.*)$/);
    if (field) frontmatter[field[1]] = field[2].replace(/^["']|["']$/g, "");
  }
  return { frontmatter, content: text.slice(match[0].length) };
}

function loadSkills() {
  if (!fs.existsSync(skillsDir)) return [];
  const skills = [];
  for (const entry of fs.readdirSync(skillsDir, { withFileTypes: true })) {
    if (!entry.isDirectory() || entry.name.startsWith(".")) continue;
    const skillPath = path.join(skillsDir, entry.name, "SKILL.md");
    if (!fs.existsSync(skillPath)) continue;
    const { frontmatter, content } = parseFrontmatter(fs.readFileSync(skillPath, "utf8"));
    skills.push({
      id: entry.name,
      name: frontmatter.name || entry.name,
      ...(frontmatter.description ? { description: frontmatter.description } : {}),
      path: skillPath,
      content,
    });
  }
  return skills;
}

// OpenCode V1: add the folder to `skills.paths`, and the host discovers SKILL.md itself.
export const ArchitectureDiagramGeneratorPlugin = async () => ({
  config: async (config) => {
    if (Array.isArray(config.skills)) return;
    config.skills = config.skills || {};
    config.skills.paths = config.skills.paths || [];
    if (!config.skills.paths.includes(skillsDir)) config.skills.paths.push(skillsDir);
  },
});

// OpenCode V2: register each skill through the skill API. V1 hosts also expose
// `skill.transform` but no `session.hook` and no `draft.add`, so both are checked.
async function setup(ctx) {
  if (!ctx || !ctx.skill || typeof ctx.skill.transform !== "function") return;
  if (!ctx.session || typeof ctx.session.hook !== "function") return;
  const skills = loadSkills();
  await ctx.skill.transform((draft) => {
    if (!draft || typeof draft.add !== "function") return;
    for (const skill of skills) {
      try {
        draft.add(skill);
      } catch (err) {
        console.error(`[architecture-diagram-generator] skill "${skill.id}" rejected by host:`, err);
      }
    }
  });
}

export default {
  id: "architecture-diagram-generator",
  server: ArchitectureDiagramGeneratorPlugin,
  setup,
};
