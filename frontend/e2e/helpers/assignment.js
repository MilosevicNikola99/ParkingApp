import { spawnSync } from "node:child_process";

export function runDueAssignment() {
  const composeProject = process.env.E2E_COMPOSE_PROJECT || "parkingappe2e";
  if (!/^[A-Za-z0-9][A-Za-z0-9_-]*$/.test(composeProject)) {
    throw new Error("E2E_COMPOSE_PROJECT contains unsupported characters.");
  }
  const composeCommand = process.env.E2E_COMPOSE_COMMAND
    || (process.platform === "win32" ? "docker-compose.exe" : "docker");
  if (!["docker", "docker-compose", "docker-compose.exe"].includes(composeCommand)) {
    throw new Error("E2E_COMPOSE_COMMAND must be docker or docker-compose.");
  }
  const composeArguments = composeCommand === "docker" ? ["compose"] : [];
  const result = spawnSync(
    composeCommand,
    [
      ...composeArguments,
      "-p",
      composeProject,
      "exec",
      "-T",
      "backend",
      "python",
      "-m",
      "app.commands.assign_due_availabilities",
      "--limit",
      "100",
    ],
    {
      cwd: new URL("../../../", import.meta.url),
      encoding: "utf8",
      timeout: 60_000,
    },
  );

  if (result.status !== 0) {
    const safeDiagnostic = [result.stdout, result.stderr]
      .filter(Boolean)
      .join("\n")
      .slice(-1500);
    throw new Error(`Assignment command failed with exit code ${result.status}.\n${safeDiagnostic}`);
  }

  const summary = result.stdout.trim();
  if (!/assigned=1\b/.test(summary) || !/failed=0\b/.test(summary)) {
    throw new Error(`Assignment command returned an unexpected summary: ${summary}`);
  }

  return summary;
}
