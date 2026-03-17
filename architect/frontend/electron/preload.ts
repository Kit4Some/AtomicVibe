import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("electronAPI", {
  getBackendPort: (): Promise<number> => ipcRenderer.invoke("get-backend-port"),
  minimizeWindow: () => ipcRenderer.send("window-minimize"),
  maximizeWindow: () => ipcRenderer.send("window-maximize"),
  closeWindow: () => ipcRenderer.send("window-close"),
  openTerminal: (cwd: string) => ipcRenderer.send("open-terminal", cwd),
  openEditor: (editor: string, cwd: string) => ipcRenderer.send("open-editor", editor, cwd),
});
