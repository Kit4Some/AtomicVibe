import { useState } from "react";
import { Folder, File, ChevronDown, ChevronRight } from "lucide-react";
import type { FileTreeNode } from "../api/types";

interface FileTreeProps {
  node: FileTreeNode;
  onSelect: (path: string) => void;
  selectedPath?: string;
  depth?: number;
}

export default function FileTree({
  node,
  onSelect,
  selectedPath,
  depth = 0,
}: FileTreeProps) {
  const [expanded, setExpanded] = useState(depth < 2);
  const isDir = node.type === "directory";
  const isSelected = node.path === selectedPath;

  const handleClick = () => {
    if (isDir) {
      setExpanded(!expanded);
    } else {
      onSelect(node.path);
    }
  };

  return (
    <div>
      <button
        onClick={handleClick}
        className={`flex w-full items-center gap-1.5 rounded-[var(--radius-sm)] px-2 py-1 text-left text-[13px] hover:bg-ds-surface-hover ${
          isSelected ? "bg-ds-accent-subtle text-ds-accent" : "text-ds-text-secondary"
        }`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        <span className="w-4 flex-shrink-0 text-ds-icon">
          {isDir ? (
            expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />
          ) : (
            <span className="inline-block w-3.5" />
          )}
        </span>
        <span className="text-ds-icon flex-shrink-0">
          {isDir ? <Folder size={14} /> : <File size={14} />}
        </span>
        <span className="truncate">{node.name}</span>
      </button>
      {isDir && expanded && node.children && (
        <div>
          {node.children.map((child) => (
            <FileTree
              key={child.path}
              node={child}
              onSelect={onSelect}
              selectedPath={selectedPath}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}
