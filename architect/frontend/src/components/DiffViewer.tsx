import ReactDiffViewer, { DiffMethod } from "react-diff-viewer-continued";

interface DiffViewerProps {
  oldValue: string;
  newValue: string;
  fileName: string;
}

export default function DiffViewer({
  oldValue,
  newValue,
  fileName,
}: DiffViewerProps) {
  return (
    <div className="overflow-auto rounded-lg border border-gray-700">
      <div className="border-b border-gray-700 bg-gray-800 px-4 py-2 text-sm font-mono text-gray-300">
        {fileName}
      </div>
      <ReactDiffViewer
        oldValue={oldValue}
        newValue={newValue}
        splitView={false}
        compareMethod={DiffMethod.LINES}
        useDarkTheme
        styles={{
          diffContainer: { fontSize: "13px" },
        }}
      />
    </div>
  );
}
