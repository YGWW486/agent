import { DiffEditor } from '@monaco-editor/react'

interface DiffViewerProps {
  original: string
  modified: string
  language?: string
}

export function DiffViewer({ original, modified, language = 'python' }: DiffViewerProps) {
  if (!original && !modified) {
    return <p className="text-xs text-text-muted py-4 text-center">No diff data available.</p>
  }

  return (
    <div className="rounded-md border border-white/8 overflow-hidden">
      <DiffEditor
        height="400px"
        language={language}
        original={original}
        modified={modified}
        options={{
          readOnly: true,
          renderSideBySide: true,
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          fontSize: 13,
          lineNumbers: 'on',
          folding: true,
          wordWrap: 'on',
          padding: { top: 8 },
        }}
        theme="vs-dark"
      />
    </div>
  )
}
