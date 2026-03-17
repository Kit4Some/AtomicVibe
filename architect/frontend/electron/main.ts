import { app, BrowserWindow, dialog, ipcMain } from "electron";
import { ChildProcess, spawn } from "node:child_process";
import http from "node:http";
import path from "node:path";

const BACKEND_PORT = 18080;
const HEALTH_URL = `http://127.0.0.1:${BACKEND_PORT}/api/health`;
const HEALTH_POLL_INTERVAL = 500;
const HEALTH_MAX_WAIT = 30_000;

let backendProcess: ChildProcess | null = null;
let mainWindow: BrowserWindow | null = null;

function isPortInUse(): Promise<boolean> {
  return new Promise((resolve) => {
    const req = http.get(HEALTH_URL, (res) => {
      resolve(res.statusCode === 200);
    });
    req.on("error", () => resolve(false));
    req.setTimeout(1000, () => {
      req.destroy();
      resolve(false);
    });
  });
}

function startBackend(): ChildProcess {
  const proc = spawn("architect", ["serve", "--port", String(BACKEND_PORT)], {
    stdio: "pipe",
    shell: true,
  });

  proc.stdout?.on("data", (data: Buffer) => {
    console.log(`[backend] ${data.toString().trim()}`);
  });

  proc.stderr?.on("data", (data: Buffer) => {
    console.error(`[backend] ${data.toString().trim()}`);
  });

  proc.on("error", (err) => {
    console.error("Failed to start backend:", err);
    dialog.showErrorBox(
      "ARCHITECT — Backend Error",
      `Failed to start the backend server.\n\n${err.message}\n\nMake sure 'architect' is installed and available on PATH.`,
    );
    app.quit();
  });

  proc.on("exit", (code) => {
    console.log(`Backend exited with code ${code}`);
    backendProcess = null;
  });

  return proc;
}

function waitForBackend(): Promise<void> {
  return new Promise((resolve, reject) => {
    const start = Date.now();

    const poll = () => {
      const req = http.get(HEALTH_URL, (res) => {
        if (res.statusCode === 200) {
          resolve();
        } else {
          retry();
        }
      });
      req.on("error", retry);
      req.setTimeout(2000, () => {
        req.destroy();
        retry();
      });
    };

    const retry = () => {
      if (Date.now() - start > HEALTH_MAX_WAIT) {
        reject(new Error("Backend did not become ready in time"));
        return;
      }
      setTimeout(poll, HEALTH_POLL_INTERVAL);
    };

    poll();
  });
}

function killBackend(): void {
  if (!backendProcess) return;
  const pid = backendProcess.pid;
  if (pid) {
    if (process.platform === "win32") {
      spawn("taskkill", ["/pid", String(pid), "/T", "/F"], { stdio: "ignore" });
    } else {
      backendProcess.kill("SIGTERM");
    }
  }
  backendProcess = null;
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    frame: false,
    transparent: true,
    hasShadow: false,
    title: "ARCHITECT",
    webPreferences: {
      preload: path.join(__dirname, "../preload/preload.mjs"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (process.env.ELECTRON_RENDERER_URL) {
    mainWindow.loadURL(process.env.ELECTRON_RENDERER_URL);
  } else {
    mainWindow.loadFile(path.join(__dirname, "../renderer/index.html"));
  }

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

// IPC: backend port
ipcMain.handle("get-backend-port", () => BACKEND_PORT);

// IPC: window controls
ipcMain.on("window-minimize", () => mainWindow?.minimize());

ipcMain.on("window-maximize", () => {
  if (mainWindow?.isMaximized()) mainWindow.unmaximize();
  else mainWindow?.maximize();
});

ipcMain.on("window-close", () => mainWindow?.close());

// IPC: open external terminal
ipcMain.on("open-terminal", (_event, cwd: string) => {
  if (process.platform === "win32") {
    spawn("cmd.exe", ["/c", "start", "cmd.exe"], { cwd, shell: true, detached: true, stdio: "ignore" });
  } else if (process.platform === "darwin") {
    spawn("open", ["-a", "Terminal", cwd], { detached: true, stdio: "ignore" });
  } else {
    spawn("x-terminal-emulator", [], { cwd, detached: true, stdio: "ignore" });
  }
});

// IPC: open code editor
ipcMain.on("open-editor", (_event, editor: string, cwd: string) => {
  spawn(editor, ["."], { cwd, shell: true, detached: true, stdio: "ignore" });
});

app.whenReady().then(async () => {
  try {
    const alreadyRunning = await isPortInUse();
    if (!alreadyRunning) {
      backendProcess = startBackend();
    } else {
      console.log("[main] Backend already running on port", BACKEND_PORT);
    }
    await waitForBackend();
    createWindow();
  } catch (err) {
    dialog.showErrorBox(
      "ARCHITECT — Startup Error",
      `Could not start the application.\n\n${err instanceof Error ? err.message : String(err)}`,
    );
    app.quit();
  }
});

app.on("window-all-closed", () => {
  killBackend();
  app.quit();
});

app.on("before-quit", () => {
  killBackend();
});
