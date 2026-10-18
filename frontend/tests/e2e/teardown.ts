import { execSync } from "node:child_process";

// Drop the browser-test schema from the BI database after the run.
export default function teardown() {
  execSync("uv run --quiet python -m tests.e2e_schema drop", {
    cwd: new URL("../../../backend", import.meta.url).pathname,
    env: { ...process.env, DB_SCHEMA: "app_test_e2e" },
    stdio: "inherit",
  });
}
