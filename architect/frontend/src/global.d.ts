interface ElectronAPI {
  getBackendPort: () => Promise<number>;
  minimizeWindow: () => void;
  maximizeWindow: () => void;
  closeWindow: () => void;
  openTerminal: (cwd: string) => void;
  openEditor: (editor: string, cwd: string) => void;
}

interface Window {
  electronAPI?: ElectronAPI;
}
