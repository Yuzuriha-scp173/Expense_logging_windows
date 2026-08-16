const { app, BrowserWindow, dialog, shell } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const http = require("http");
const net = require("net");

const ROOT = path.join(__dirname, "..");
const DEV_UI = process.env.DAYBOOK_DEV_UI || "http://127.0.0.1:5173";
const DEV_API = process.env.DAYBOOK_DEV_API || "http://127.0.0.1:8765";

let backendProcess = null;
let mainWindow = null;

function standalone() {
  return app.isPackaged || process.env.DAYBOOK_STANDALONE === "1";
}

function pythonBin() {
  const bins = [];
  if (app.isPackaged) {
    bins.push(path.join(process.resourcesPath, "backend", "daybook-api.exe"));
    bins.push(path.join(process.resourcesPath, "backend", "daybook-api"));
    bins.push(path.join(process.resourcesPath, "backend", ".venv", "Scripts", "python.exe"));
    bins.push(path.join(process.resourcesPath, "backend", ".venv", "bin", "python"));
  }
  bins.push(path.join(ROOT, "backend", ".venv", "Scripts", "python.exe"));
  bins.push(path.join(ROOT, "backend", ".venv", "bin", "python"));
  bins.push(path.join(ROOT, "backend", ".venv", "bin", "python3"));
  for (const bin of bins) {
    if (fs.existsSync(bin)) return bin;
  }
  return process.platform === "win32" ? "python" : "python3";
}

function backendDir() {
  if (app.isPackaged) {
    const packaged = path.join(process.resourcesPath, "backend");
    if (fs.existsSync(packaged)) return packaged;
  }
  return path.join(ROOT, "backend");
}

function uiDir() {
  if (app.isPackaged) {
    const packaged = path.join(process.resourcesPath, "ui");
    if (fs.existsSync(packaged)) return packaged;
  }
  return path.join(ROOT, "frontend", "dist");
}

function pickPort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
    server.on("error", reject);
  });
}

function waitForHealth(url, timeoutMs = 25000) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const tick = () => {
      const req = http.get(`${url}/api/health`, (res) => {
        if (res.statusCode === 200) resolve();
        else if (Date.now() - started > timeoutMs) reject(new Error("Backend did not become healthy"));
        else setTimeout(tick, 250);
      });
      req.on("error", () => {
        if (Date.now() - started > timeoutMs) reject(new Error("Backend did not start"));
        else setTimeout(tick, 250);
      });
    };
    tick();
  });
}

function logBackend(chunk) {
  try {
    const file = path.join(app.getPath("userData"), "backend.log");
    fs.appendFileSync(file, chunk);
  } catch {
    /* ignore */
  }
}

async function startBackend() {
  if (!standalone()) {
    await waitForHealth(DEV_API);
    await waitForHealth(DEV_UI);
    return DEV_API;
  }

  const port = await pickPort();
  const py = pythonBin();
  const cwd = backendDir();
  const ui = uiDir();
  const env = {
    ...process.env,
    EXPENSE_DATA_DIR: app.getPath("userData"),
    DAYBOOK_UI: ui,
    API_HOST: "127.0.0.1",
    API_PORT: String(port),
    PYTHONUNBUFFERED: "1",
  };
  const args = path.basename(py).includes("daybook-api")
    ? []
    : ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", String(port)];

  backendProcess = spawn(py, args, { cwd, env, stdio: "pipe", windowsHide: true });
  backendProcess.stderr?.on("data", (d) => logBackend(String(d)));
  backendProcess.stdout?.on("data", (d) => logBackend(String(d)));
  backendProcess.on("error", (err) => logBackend(String(err)));

  const url = `http://127.0.0.1:${port}`;
  await waitForHealth(url);
  return url;
}

async function createWindow() {
  let uiUrl;
  try {
    const apiUrl = await startBackend();
    uiUrl = standalone() ? apiUrl : DEV_UI;
  } catch (err) {
    dialog.showErrorBox(
      "Daybook couldn’t start",
      `${err.message}\n\nOpen Command Prompt or PowerShell, cd into the Daybook folder, and run:\nnpm run install:desktop`,
    );
    app.quit();
    return;
  }

  const icon = path.join(ROOT, "build", "icon.png");
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 840,
    minWidth: 860,
    minHeight: 640,
    title: "Daybook",
    backgroundColor: "#f4f1eb",
    icon: fs.existsSync(icon) ? icon : undefined,
    titleBarStyle: process.platform === "darwin" ? "hiddenInset" : "default",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
  await mainWindow.loadURL(uiUrl);
}

app.setName("Daybook");
app.setPath("userData", path.join(app.getPath("appData"), "Daybook"));
app.whenReady().then(async () => {
  if (process.platform === "darwin" && app.dock) {
    const icon = path.join(ROOT, "build", "icon.png");
    if (fs.existsSync(icon)) app.dock.setIcon(icon);
  }
  await createWindow();
}).catch((err) => {
  dialog.showErrorBox("Daybook couldn’t start", String(err));
  app.quit();
});

app.on("window-all-closed", () => {
  if (backendProcess) backendProcess.kill();
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  if (backendProcess) backendProcess.kill();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
