const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

const rootDir = path.resolve(__dirname, "..");

// Try project virtual environment python first, then fallback to global python
const venvPyWin = path.resolve(rootDir, ".venv", "Scripts", "python.exe");
const venvPyUnix = path.resolve(rootDir, ".venv", "bin", "python");

let pythonCmd = "python";
if (fs.existsSync(venvPyWin)) {
  pythonCmd = venvPyWin;
} else if (fs.existsSync(venvPyUnix)) {
  pythonCmd = venvPyUnix;
}

const apiPath = path.resolve(rootDir, "api_server.py");
console.log(`[BACKEND] Starting Verity FastAPI backend using: ${pythonCmd}`);

const proc = spawn(pythonCmd, [apiPath], {
  cwd: rootDir,
  stdio: "inherit",
  env: { ...process.env, PYTHONPATH: rootDir },
});

proc.on("exit", (code) => {
  process.exit(code || 0);
});
