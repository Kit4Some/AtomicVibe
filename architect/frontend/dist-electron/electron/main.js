"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const electron_1 = require("electron");
const node_child_process_1 = require("node:child_process");
const node_http_1 = __importDefault(require("node:http"));
const node_path_1 = __importDefault(require("node:path"));
const BACKEND_PORT = 18080;
const HEALTH_URL = `http://127.0.0.1:${BACKEND_PORT}/api/health`;
const HEALTH_POLL_INTERVAL = 500;
const HEALTH_MAX_WAIT = 30_000;
let backendProcess = null;
let mainWindow = null;
function startBackend() {
    const proc = (0, node_child_process_1.spawn)("architect", ["serve", "--port", String(BACKEND_PORT)], {
        stdio: "pipe",
        shell: true,
    });
    proc.stdout?.on("data", (data) => {
        console.log(`[backend] ${data.toString().trim()}`);
    });
    proc.stderr?.on("data", (data) => {
        console.error(`[backend] ${data.toString().trim()}`);
    });
    proc.on("error", (err) => {
        console.error("Failed to start backend:", err);
        electron_1.dialog.showErrorBox("ARCHITECT — Backend Error", `Failed to start the backend server.\n\n${err.message}\n\nMake sure 'architect' is installed and available on PATH.`);
        electron_1.app.quit();
    });
    proc.on("exit", (code) => {
        console.log(`Backend exited with code ${code}`);
        backendProcess = null;
    });
    return proc;
}
function waitForBackend() {
    return new Promise((resolve, reject) => {
        const start = Date.now();
        const poll = () => {
            const req = node_http_1.default.get(HEALTH_URL, (res) => {
                if (res.statusCode === 200) {
                    resolve();
                }
                else {
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
function createWindow() {
    mainWindow = new electron_1.BrowserWindow({
        width: 1400,
        height: 900,
        minWidth: 900,
        minHeight: 600,
        title: "ARCHITECT",
        webPreferences: {
            preload: node_path_1.default.join(__dirname, "../preload/preload.mjs"),
            contextIsolation: true,
            nodeIntegration: false,
        },
    });
    // In dev mode, electron-vite serves on localhost
    if (process.env.ELECTRON_RENDERER_URL) {
        mainWindow.loadURL(process.env.ELECTRON_RENDERER_URL);
    }
    else {
        mainWindow.loadFile(node_path_1.default.join(__dirname, "../renderer/index.html"));
    }
    mainWindow.on("closed", () => {
        mainWindow = null;
    });
}
// IPC: renderer can ask for the backend port
electron_1.ipcMain.handle("get-backend-port", () => BACKEND_PORT);
electron_1.app.whenReady().then(async () => {
    try {
        backendProcess = startBackend();
        await waitForBackend();
        createWindow();
    }
    catch (err) {
        electron_1.dialog.showErrorBox("ARCHITECT — Startup Error", `Could not start the application.\n\n${err instanceof Error ? err.message : String(err)}`);
        electron_1.app.quit();
    }
});
electron_1.app.on("window-all-closed", () => {
    if (backendProcess) {
        backendProcess.kill();
        backendProcess = null;
    }
    electron_1.app.quit();
});
electron_1.app.on("before-quit", () => {
    if (backendProcess) {
        backendProcess.kill();
        backendProcess = null;
    }
});
