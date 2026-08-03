import { spawn } from "node:child_process";
import { request as httpRequest } from "node:http";
import { createServer } from "node:net";
import { join } from "node:path";

async function availablePort() {
  const server = createServer();
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  const address = server.address();
  await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  if (!address || typeof address === "string") {
    throw new Error("Could not reserve a loopback port for the HTTP smoke test.");
  }
  return String(address.port);
}

const port = process.env.ACP_WEB_SMOKE_PORT ?? await availablePort();
const token = "wiki-llm-http-smoke-token";
const baseUrl = `http://127.0.0.1:${port}`;

const child = spawn(process.execPath, [join(process.cwd(), "node_modules/next/dist/bin/next"), "start", "--hostname", "127.0.0.1", "--port", port], {
  env: {
    ...process.env,
    ACP_WEB_TOKEN: token,
    NEXT_PUBLIC_ACP_WEB_TOKEN: token,
    ACP_WORKSPACE: join(process.cwd(), "../.."),
  },
  stdio: ["ignore", "pipe", "pipe"],
});

let output = "";
child.stdout.on("data", (chunk) => {
  output += chunk;
});
child.stderr.on("data", (chunk) => {
  output += chunk;
});

async function waitForServer() {
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${baseUrl}/api/config`);
      if (response.status === 401) return;
    } catch {
      // The server is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error(`Agent desk did not start within 30 seconds.\n${output}`);
}

async function assertStatus(path, options, expected) {
  const response = await fetch(`${baseUrl}${path}`, options);
  if (response.status !== expected) {
    throw new Error(
      `${options?.method ?? "GET"} ${path}: expected ${expected}, got ${response.status}: ${await response.text()}\n${output}`,
    );
  }
}

async function assertRejectedHost() {
  const response = await new Promise((resolve, reject) => {
    const request = httpRequest(`${baseUrl}/api/config`, {
      headers: {
        Authorization: `Bearer ${token}`,
        Host: "example.com",
      },
    }, resolve);
    request.once("error", reject);
    request.end();
  });
  if (response.statusCode !== 403) {
    throw new Error(`GET /api/config with a non-loopback Host: expected 403, got ${response.statusCode}`);
  }
  response.resume();
}

async function stopServer() {
  if (child.exitCode !== null) return;
  const closed = new Promise((resolve) => child.once("close", () => resolve(true)));
  child.kill("SIGTERM");
  const stopped = await Promise.race([
    closed,
    new Promise((resolve) => setTimeout(() => resolve(false), 5_000)),
  ]);
  if (!stopped && child.exitCode === null) {
    const forcedClosed = new Promise((resolve) => child.once("close", () => resolve()));
    child.kill("SIGKILL");
    await forcedClosed;
  }
}

try {
  await waitForServer();
  await assertStatus("/api/config", undefined, 401);
  await assertStatus(
    "/api/config",
    { headers: { Authorization: `Bearer ${token}` } },
    200,
  );
  await assertRejectedHost();
  await assertStatus(
    "/api/chat",
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "content-type": "application/json",
      },
      body: "{}",
    },
    400,
  );
  await assertStatus(
    "/api/chat",
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "content-type": "application/json",
      },
      body: "null",
    },
    400,
  );
  await assertStatus(
    "/api/chat",
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({ messages: [null] }),
    },
    400,
  );
  await assertStatus(
    "/api/chat",
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({
        messages: [{ role: "user", parts: [{ type: "text", text: "hello" }] }],
        sessionName: 7,
      }),
    },
    400,
  );
  await assertStatus(
    "/api/chat",
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "content-type": "application/json",
      },
      body: "{",
    },
    400,
  );
  console.log("Agent desk HTTP smoke: OK");
} finally {
  await stopServer();
}
