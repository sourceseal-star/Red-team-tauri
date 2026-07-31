import { useEffect, useState } from 'react'
import { invoke } from '@tauri-apps/api/tauri'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Save, RefreshCw } from 'lucide-react'

interface ConfigFile { name: string; path: string }

export default function ConfigEditor() {
  const [files, setFiles] = useState<ConfigFile[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [content, setContent] = useState('')
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    invoke('get_config_files').then(f => setFiles(f as ConfigFile[]))
  }, [])

  const load = async (path: string) => {
    setSelected(path)
    const c = await invoke('read_config_file', { path }) as string
    setContent(c)
    setSaved(false)
  }

  const save = async () => {
    await invoke('write_config_file', { path: selected, content })
    setSaved(true)
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold">Config Editor</h2>
      <div className="grid grid-cols-4 gap-4 h-[calc(100vh-12rem)]">
        <Card className="col-span-1 overflow-y-auto">
          <CardHeader><CardTitle>Files</CardTitle></CardHeader>
          <CardContent className="p-2 space-y-1">
            {files.map(f => (
              <button
                key={f.path}
                onClick={() => load(f.path)}
                className={`w-full text-left text-xs px-2 py-1.5 rounded transition-colors font-mono ${selected === f.path ? 'bg-blue-600/20 text-blue-400' : 'hover:bg-accent'}`}
              >
                {f.name}
              </button>
            ))}
          </CardContent>
        </Card>

        <Card className="col-span-3 flex flex-col">
          <CardHeader className="pb-2 flex-row items-center justify-between">
            <CardTitle className="font-mono text-xs">{selected ?? 'Select a file'}</CardTitle>
            {selected && (
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => load(selected!)}><RefreshCw className="h-3 w-3 mr-1" />Reload</Button>
                <Button size="sm" onClick={save}><Save className="h-3 w-3 mr-1" />{saved ? 'Saved!' : 'Save'}</Button>
              </div>
            )}
          </CardHeader>
          <CardContent className="flex-1 p-0">
            <textarea
              className="w-full h-full bg-transparent font-mono text-xs p-4 resize-none outline-none text-foreground"
              value={content}
              onChange={e => { setContent(e.target.value); setSaved(false) }}
              placeholder="Select a file to edit…"
              spellCheck={false}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
