import { useEffect, useState } from 'react'
import { api, type ConfigFile } from '../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Save, RefreshCw } from 'lucide-react'

export default function ConfigEditor() {
  const [files, setFiles]     = useState<ConfigFile[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [content, setContent] = useState('')
  const [saved, setSaved]     = useState(false)
  const [loading, setLoading] = useState(false)
  const [msg, setMsg]         = useState('')

  useEffect(() => {
    api.listConfigFiles().then(setFiles)
  }, [])

  const loadFile = async (path: string) => {
    setLoading(true)
    setSaved(false)
    setMsg('')
    try {
      const r = await api.readConfig(path)
      setSelected(path)
      setContent(r.content)
    } catch (e) {
      setMsg(`Error: ${e}`)
    } finally {
      setLoading(false)
    }
  }

  const save = async () => {
    if (!selected) return
    try {
      await api.writeConfig(selected, content)
      setSaved(true)
      setMsg('✓ Guardado')
      setTimeout(() => { setSaved(false); setMsg('') }, 3000)
    } catch (e) {
      setMsg(`Error al guardar: ${e}`)
    }
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold">Config Editor</h2>
      {msg && <div className={`text-sm rounded px-3 py-2 border ${msg.startsWith('✓') ? 'text-green-400 bg-green-900/20 border-green-800' : 'text-red-400 bg-red-900/20 border-red-800'}`}>{msg}</div>}
      <div className="grid grid-cols-4 gap-4 h-[calc(100vh-14rem)]">
        {/* File list */}
        <Card className="col-span-1 overflow-y-auto">
          <CardHeader><CardTitle>Archivos</CardTitle></CardHeader>
          <CardContent className="p-2 space-y-1">
            {files.map(f => (
              <button key={f.path} onClick={() => loadFile(f.path)}
                className={`w-full text-left text-xs px-2 py-1.5 rounded transition-colors font-mono truncate ${
                  selected === f.path ? 'bg-blue-600/20 text-blue-400' : 'hover:bg-accent'}`}>
                {f.name}
                {f.size !== undefined && (
                  <span className="block text-[10px] text-muted-foreground">{(f.size / 1024).toFixed(1)} KB</span>
                )}
              </button>
            ))}
          </CardContent>
        </Card>

        {/* Editor */}
        <Card className="col-span-3 flex flex-col">
          <CardHeader className="pb-2 flex-row items-center justify-between shrink-0">
            <CardTitle className="font-mono text-xs truncate">{selected ?? 'Selecciona un archivo'}</CardTitle>
            {selected && (
              <div className="flex gap-2 shrink-0">
                <Button size="sm" variant="outline" onClick={() => loadFile(selected)} disabled={loading}>
                  <RefreshCw className={`h-3 w-3 mr-1 ${loading ? 'animate-spin' : ''}`} />Recargar
                </Button>
                <Button size="sm" onClick={save} disabled={!selected}>
                  <Save className="h-3 w-3 mr-1" />{saved ? 'Guardado ✓' : 'Guardar'}
                </Button>
              </div>
            )}
          </CardHeader>
          <CardContent className="flex-1 p-0 overflow-hidden">
            <textarea
              className="w-full h-full bg-transparent font-mono text-xs p-4 resize-none outline-none text-foreground leading-relaxed"
              value={content}
              onChange={e => { setContent(e.target.value); setSaved(false) }}
              placeholder="Selecciona un archivo para editar…"
              spellCheck={false}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
