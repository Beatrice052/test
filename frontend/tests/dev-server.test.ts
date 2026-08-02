// @vitest-environment node

import { afterEach, describe, expect, it } from "vitest";
import { createServer, type ViteDevServer } from "vite";

describe("Phase 0 Vite server", () => {
  let server: ViteDevServer | undefined;

  afterEach(async () => {
    await server?.close();
  });

  it("serves the application shell over HTTP", async () => {
    server = await createServer({
      configFile: false,
      root: process.cwd(),
      logLevel: "silent",
      server: { host: "127.0.0.1", port: 0 },
    });
    await server.listen();

    const address = server.httpServer?.address();
    if (address === null || address === undefined || typeof address === "string") {
      throw new Error("Vite did not expose a TCP address");
    }

    const response = await fetch(`http://127.0.0.1:${address.port}/`);
    const html = await response.text();

    expect(response.status).toBe(200);
    expect(html).toContain("OpenSearch ChatBI V6.1");
  });
});

