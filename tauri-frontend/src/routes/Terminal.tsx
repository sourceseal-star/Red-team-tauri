import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { Button } from '../components/ui/button'
import { Send, Trash2 } from 'lucide-react'

interface Line { type: 'cmd' | 'out' | 'err' | 'info'; text: string }

const ALLOWED = ['ls','cat','pwd','echo','grep','find','ps','df','free','uname',
                 'date','id','whoami','netstat','ss','hostname','env','python3',
                 'pip','git','head','tail','wc','sort','uniq','cut','awk','sed',
                 'top','uptime','which']

export default function Terminal() {
  const [input, setInput]   = useState('')
  const [loading, setLoading] = useState(false)
  const [history, setHistory] = useState<string[]>([])
  const [histIdx, setHistIdx] = useState(-1)
  const [lines, setLines]   = useState<Line[]>([
    { type: 'info', text: '── SourceSeal Console — Terminal ──────────────────────────────' },
    { type: 'info', text: `Comandos permitidos: ${ALLOWED.join(', ')}` },
    { type: 'info', text: 'Los comandos se ejecutan en el servidor (directorio redteam/).' },
    { type: 'info', text: '──────────────────────────────────────────────────────────────' },
  ])
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines])

  const add = (type: Line['type'], text: string) =>
    setLines(l => [...l, { type, text }])

  const run = async () => {
    const cmd = input.trim()
    if (!cmd || loading) return
    setHistory(h => [cmd, ...h.slice(0, 49)])
    setHistIdx(-1)
    setInput('')
    add('cmd', `$ ${cmd}`)
    setLoading(true)
    try {
      const r = await api.runCommand(cmd)
      if (r.stdout) r.stdout.trimEnd().split('\n').forEach(l => add('out', l))
      if (r.stderr) r.stderr.trimEnd().split('\n').forEach(l => add('err', l))
      if (!r.stdout && !r.stderr) add('out', '(sin salida)')
      if (r.code !== 0) add('err', `[exit ${r.code}]`)
    } catch (e) {
      add('err', String(e))
    } finally {
      setLoading(false)
    }
  }

  const onKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') { run(); return }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      const next = Math.min(histIdx + 1, history.length - 1)
      setHistIdx(next)
      setInput(history[next] ?? '')
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      const next = Math.max(histIdx - 1, -1)
      setHistIdx(next)
      setInput(next === -1 ? '' : history[next])
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-10rem)] space-y-2">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Terminal</h2>
        <Button size="sm" variant="ghost" onClick={() => setLines(l => l.slice(0, 4))}>
          <Trash2 className="h-3 w-3 mr-1" />Limpiar
        </Button>
      </div>

      <div className="flex-1 bg-black rounded-lg p-3 overflow-y-auto font-mono text-xs leading-relaxed">
        {lines.map((l, i) => (
          <div key={i} className={
            l.type === 'cmd'  ? 'text-cyan-400' :
            l.type === 'err'  ? 'text-red-400' :
            l.type === 'info' ? 'text-gray-500' :
            'text-green-300'
          }>
            {l.text}
          </div>
        ))}
        {loading && <div className="text-yellow-400 animate-pulse">ejecutando…</div>}
        <div ref={bottomRef} />
      </div>

      <div className="flex gap-2">
        <input
          className="flex-1 bg-zinc-900 border border-zinc-700 rounded-md px-3 py-2 font-mono text-sm outline-none focus:ring-1 focus:ring-cyan-500 text-green-300"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={onKey}
          placeholder="$ comando…  (↑↓ para historial)"
          spellCheck={false}
          disabled={loading}
          autoComplete="off"
        />
        <Button onClick={run} disabled={loading || !input.trim()} className="bg-cyan-700 hover:bg-cyan-600">
          <Send className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}
