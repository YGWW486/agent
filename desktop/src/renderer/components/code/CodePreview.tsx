import { Editor } from '@monaco-editor/react'

interface CodePreviewProps {
  code: string
  language?: string
  height?: string
}

export function CodePreview({ code, language = 'python', height = '200px' }: CodePreviewProps) {
  if (!code) {
    return <p className="text-xs text-text-muted py-4 text-center">No code to display.</p>
  }

  return (
    <div className="rounded-md border border-white/8 overflow-hidden">
      <Editor
        height={height}
        language={language}
        value={code}
        options={{
          readOnly: true,
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          fontSize: 13,
          lineNumbers: 'on',
          folding: true,
          wordWrap: 'on',
          padding: { top: 8 },
          renderLineHighlight: 'none',
        }}
        theme="vs-dark"
      />
    </div>
  )
}
