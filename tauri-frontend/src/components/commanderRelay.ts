export async function resolveCommanderResponse(
  response: Response,
  headers: Record<string, string>,
): Promise<any> {
  let data: any = await response.json().catch(() => ({}))
  if (!response.ok && response.status !== 202) {
    throw new Error(data.detail || data.error || `HTTP ${response.status}`)
  }
  if (response.status !== 202 || !data.task_id) return data

  const taskId = String(data.task_id)
  const deadline = Date.now() + 15 * 60 * 1000
  while (Date.now() < deadline) {
    await new Promise(resolve => setTimeout(resolve, 2000))
    const statusResponse = await fetch(
      `/api/commander/tasks/${encodeURIComponent(taskId)}`,
      { headers, cache: 'no-store' },
    )
    data = await statusResponse.json().catch(() => ({}))
    if (!statusResponse.ok) {
      throw new Error(data.error || `No se pudo consultar la tarea (${statusResponse.status})`)
    }
    if (data.status === 'completed') return data.result ?? data
    if (data.status === 'failed' || data.ok === false) {
      throw new Error(data.error || 'La tarea falló en Termux')
    }
    if (data.status !== 'queued' && data.status !== 'running') {
      throw new Error('El relé devolvió un estado de tarea no reconocido')
    }
  }
  throw new Error('Termux no terminó la tarea dentro del tiempo esperado')
}