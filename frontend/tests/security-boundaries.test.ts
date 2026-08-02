// @vitest-environment node

import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

async function sourceFiles(directory: string): Promise<Array<string>> {
  const entries = await readdir(directory, { withFileTypes: true });
  const nested = await Promise.all(entries.map(async (entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return sourceFiles(path);
    return entry.name.endsWith(".ts") || entry.name.endsWith(".tsx") ? [path] : [];
  }));
  return nested.flat();
}

describe("browser trust boundary", () => {
  it("contains no raw HTML or dynamic-code execution sinks", async () => {
    const files = (await sourceFiles(join(process.cwd(), "src"))).filter(
      (path) => !path.endsWith("generated.ts"),
    );
    const source = (await Promise.all(files.map((path) => readFile(path, "utf8")))).join("\n");

    expect(source).not.toContain("dangerouslySetInnerHTML");
    expect(source).not.toMatch(/\beval\s*\(/u);
    expect(source).not.toContain("new Function");
    expect(source).not.toContain("raw_option");
  });
});
