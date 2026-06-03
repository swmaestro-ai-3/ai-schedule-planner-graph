import { spawn } from "node:child_process";

const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";

const processes = [
  {
    name: "backend",
    args: ["run", "backend:dev"],
  },
  {
    name: "frontend",
    args: ["run", "frontend:dev"],
  },
];

let shuttingDown = false;
const children = [];

function writePrefixed(name, stream, chunk) {
  const lines = chunk.toString().split(/\r?\n/);
  for (const line of lines) {
    if (line.length > 0) {
      stream.write(`[${name}] ${line}\n`);
    }
  }
}

function stopAll(signal = "SIGTERM") {
  if (shuttingDown) {
    return;
  }
  shuttingDown = true;
  for (const child of children) {
    if (!child.killed) {
      child.kill(signal);
    }
  }
}

console.log("Starting NextPlan AI dev stack");
console.log("Backend:  http://127.0.0.1:8010");
console.log("Frontend: http://127.0.0.1:5173");

for (const processConfig of processes) {
  const child = spawn(npmCommand, processConfig.args, {
    cwd: process.cwd(),
    env: process.env,
    stdio: ["inherit", "pipe", "pipe"],
  });

  children.push(child);

  child.stdout.on("data", (chunk) => {
    writePrefixed(processConfig.name, process.stdout, chunk);
  });

  child.stderr.on("data", (chunk) => {
    writePrefixed(processConfig.name, process.stderr, chunk);
  });

  child.on("error", (error) => {
    if (shuttingDown) {
      return;
    }
    console.error(`[${processConfig.name}] failed to start: ${error.message}`);
    stopAll();
    process.exit(1);
  });

  child.on("exit", (code, signal) => {
    if (shuttingDown) {
      return;
    }

    if (code === 0) {
      stopAll();
      process.exit(0);
    }

    console.error(
      `[${processConfig.name}] exited with ${signal ?? `code ${code}`}. Stopping dev stack.`,
    );
    stopAll();
    process.exit(code ?? 1);
  });
}

process.on("SIGINT", () => {
  stopAll("SIGINT");
});

process.on("SIGTERM", () => {
  stopAll("SIGTERM");
});
