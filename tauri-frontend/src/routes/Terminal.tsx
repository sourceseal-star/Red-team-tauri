import { useState } from 'react'
import { invoke } from '@tauri-apps/api/tauri'
import { Button } from '../components/ui/button'
import { Send } from 'lucide-react'

interface Line { type: 'cmd' | 'out' | 'err'; text: string }

export default function Terminal() {
  const [input, setInput] = useState('')
  const [lines, setLines] = useState<Line[]>([
    { type: 'out', text: 'SourceSeal Console — Terminal (web mode: commands are sandboxed)' },
    { type: 'out', text: 'Type a command and press Enter or click Send.' },
  ])

  const run = async () => {
    if (!input.trim()) return
    const cmd = input.trim()
    setLines(l => [...l, { type: 'cmd', text: `$ ${cmd}` }])
    setInput('')
    try {
      const r = await invoke('run_terminal_command', { command: cmd }) as { stdout: string; stderr: string; code: number }
      if (r.stdout) setLines(l => [...l, { type: 'out', text: r.stdout }])
      if (r.stderr) setLines(l => [...l, { type: 'err', text: r.stderr }])
    } catch (e) {
      setLines(l => [...l, { type: 'err', text: String(e) }])
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-10rem)] space-y-2">
      <h2 className="text-xl font-bold">Terminal</h2>
      <div className="flex-1 bg-black rounded-lg p-3 overflow-y-auto font-mono text-xs">
        {lines.map((l, i) => (
          <div key={i} className={l.type === 'cmd' ? 'text-blue-400' : l.type === 'err' ? 'text-red-400' : 'text-green-300'}>
            {l.text}
          </div>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          className="flex-1 bg-muted border border-border rounded-md px-3 py-2 font-mono text-sm outline-none focus:ring-1 focus:ring-blue-500"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && run()}
          placeholder="$ enter command…"
          spellCheck={false}
        />
        <Button onClick={run}><Send className="h-4 w-4" /></Button>
      </div>
    </div>
  )
}
