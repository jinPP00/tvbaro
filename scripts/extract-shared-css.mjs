import { createHash } from "node:crypto";
import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join, relative } from "node:path";

const root = process.cwd();
const htmlFiles = [];

function walk(directory) {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    if (entry.name === ".git" || entry.name === "node_modules") continue;
    const fullPath = join(directory, entry.name);
    if (entry.isDirectory()) walk(fullPath);
    else if (entry.name.endsWith(".html")) htmlFiles.push(fullPath);
  }
}

walk(root);

const baseIds = [
  "wp-img-auto-sizes-contain-inline-css",
  "wp-block-library-inline-css",
  "classic-theme-styles-inline-css",
  "global-styles-inline-css",
];
const themeId = "generate-style-inline-css";
const allIds = [...baseIds, themeId];
const captured = new Map();
let removedBytes = 0;
let changedFiles = 0;

for (const file of htmlFiles) {
  let html = readFileSync(file, "utf8");
  const hasBaseLink = html.includes("/assets/wp-export-base.css?v=20260813-1");
  const hasThemeLink = html.includes("/assets/generatepress-inline.css?v=20260813-1");
  let changed = false;

  for (const id of allIds) {
    const pattern = new RegExp(`<style\\s+id=["']${id}["'][^>]*>([\\s\\S]*?)<\\/style>`, "i");
    const match = html.match(pattern);
    if (!match) {
      const hasReplacement = id === themeId ? hasThemeLink : hasBaseLink;
      if (!hasReplacement) throw new Error(`${relative(root, file)}: missing ${id} and its shared stylesheet`);
      continue;
    }

    const css = match[1].trim();
    const digest = createHash("sha256").update(css).digest("hex");
    const previous = captured.get(id);
    if (previous && previous.digest !== digest) {
      throw new Error(`${relative(root, file)}: ${id} differs between pages`);
    }
    captured.set(id, { css, digest });
    removedBytes += match[0].length;

    const replacement = id === baseIds[0]
      ? '<link href="/assets/wp-export-base.css?v=20260813-1" rel="stylesheet"/>'
      : id === themeId
        ? '<link href="/assets/generatepress-inline.css?v=20260813-1" rel="stylesheet"/>'
        : "";
    html = html.replace(pattern, replacement);
    changed = true;
  }

  if (changed) {
    writeFileSync(file, html, "utf8");
    changedFiles += 1;
  }
}

if (captured.size > 0) {
  const baseCss = baseIds
    .map((id) => `/* ${id} */\n${captured.get(id).css}`)
    .join("\n\n");
  const themeCss = `/* ${themeId} */\n${captured.get(themeId).css}\n`;
  writeFileSync(join(root, "assets", "wp-export-base.css"), `${baseCss}\n`, "utf8");
  writeFileSync(join(root, "assets", "generatepress-inline.css"), themeCss, "utf8");
}

console.log(`Shared CSS extraction complete: ${changedFiles} HTML files, ${removedBytes} inline bytes removed.`);
