'use client'
import { useCallback, useEffect, useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription
} from '@/components/ui/dialog'
import {
  personalApi,
  usePersonalModels,
  type Connection
} from '@/lib/personal-models'
import { useStore } from '@/store'

export default function ModelSettings() {
  const state = usePersonalModels()
  const endpoint = useStore((s) => s.selectedEndpoint)
  const websiteEndpoint = process.env.NEXT_PUBLIC_AGENT_OS_URL
  const [name, setName] = useState('My model connection')
  const [base, setBase] = useState('https://api.deepseek.com')
  const [key, setKey] = useState('')
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const setConnections = state.setConnections
  const reload = useCallback(async () => {
    const result = await personalApi<{ items: Connection[] }>(
      '/model-connections'
    )
    setConnections(result.items)
  }, [setConnections])
  useEffect(() => {
    void reload().catch(() => undefined)
  }, [endpoint, reload]) // metadata only; no provider calls
  useEffect(() => {
    if (!state.open) setKey('')
  }, [state.open])
  async function save() {
    setBusy(true)
    setNotice('Saving your encrypted connection…')
    try {
      const row = await personalApi<Connection>('/model-connections', {
        method: 'POST',
        body: JSON.stringify({ name, base_url: base, api_key: key })
      })
      setKey('')
      await reload()
      setNotice('Discovering models from your provider…')
      const discovered = await personalApi<Connection>(
        `/model-connections/${row.id}/discover`,
        { method: 'POST' }
      )
      await reload()
      const preferred =
        discovered.models.find((m) => m === 'deepseek-flash') ||
        discovered.models.find((m) =>
          /gpt-4.1-mini|gemini.*flash|claude.*sonnet/.test(m)
        ) ||
        discovered.models[0]
      state.select(row.id, preferred)
      setNotice(
        `${discovered.models.length} models discovered. Selected ${preferred}. Sending a message uses your provider account.`
      )
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Connection failed.')
    } finally {
      setBusy(false)
    }
  }
  return (
    <Dialog open={state.open} onOpenChange={state.setOpen}>
      <DialogContent className="model-settings-dialog">
        <DialogTitle>Models & API keys</DialogTitle>
        <DialogDescription>
          Choose your own model when the shared service is unavailable. Keys are
          encrypted on this local server and never saved in browser storage.
          This browser’s chat settings do not change scheduled monitoring.
        </DialogDescription>
        <div className="model-settings-body">
          {websiteEndpoint && endpoint !== websiteEndpoint && (
            <div className="saved-connection" role="status">
              <p>
                This browser is using a previously saved application service.
                Connect to this website’s current service before managing
                personal models.
              </p>
              <button
                type="button"
                className="primary-action"
                onClick={() => {
                  useStore.getState().setSelectedEndpoint(websiteEndpoint)
                  state.select('', '')
                  setNotice('Connected to this website’s current service.')
                }}
              >
                Use this website’s service
              </button>
            </div>
          )}
          <div className="connection-presets" aria-label="Provider presets">
            <button
              type="button"
              onClick={() => {
                setBase('https://api.deepseek.com')
                setName('DeepSeek Official')
              }}
            >
              DeepSeek
            </button>
            <button
              type="button"
              onClick={() => {
                setBase('https://toapis.cn/v1')
                setName('Toapis')
              }}
            >
              Toapis · GPT / Gemini / Claude
            </button>
            <button
              type="button"
              onClick={() => {
                setBase('https://api.openai.com/v1')
                setName('OpenAI')
              }}
            >
              OpenAI-compatible
            </button>
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              void save()
            }}
          >
            <label>
              Connection name
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                maxLength={80}
              />
            </label>
            <label>
              API base URL
              <input
                type="url"
                value={base}
                onChange={(e) => setBase(e.target.value)}
                required
                placeholder="https://provider.example/v1"
              />
            </label>
            <label>
              API key
              <input
                type="password"
                autoComplete="off"
                spellCheck={false}
                value={key}
                onChange={(e) => setKey(e.target.value)}
                required
                placeholder="Enter your provider API key"
              />
            </label>
            <button
              className="primary-action"
              disabled={busy || !key.trim()}
              type="submit"
            >
              {busy ? 'Connecting…' : 'Save & discover models'}
            </button>
          </form>
          <p role="status" className="model-notice">
            {notice ||
              'Discovery reads the provider’s model list. It does not prove generation availability; models may have separate quota or channel limits.'}
          </p>
          <h3>Saved connections</h3>
          {state.connections.length === 0 && (
            <p>
              No personal connections yet. The shared service remains available
              from the model menu.
            </p>
          )}
          {state.connections.map((connection) => (
            <article key={connection.id} className="saved-connection">
              <strong>{connection.name}</strong>
              <span>{connection.key_hint}</span>
              <p>{connection.base_url}</p>
              <label>
                Available model
                <select
                  aria-label={`Model for ${connection.name}`}
                  value={
                    state.connectionId === connection.id ? state.model : ''
                  }
                  onChange={(e) => state.select(connection.id, e.target.value)}
                >
                  <option value="" disabled>
                    Select a model
                  </option>
                  {connection.models.map((model) => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))}
                </select>
              </label>
              <div className="connection-actions">
                <button
                  disabled={busy}
                  onClick={async () => {
                    setBusy(true)
                    try {
                      await personalApi(
                        `/model-connections/${connection.id}/discover`,
                        { method: 'POST' }
                      )
                      await reload()
                      setNotice('Model list refreshed.')
                    } catch (error) {
                      setNotice(String(error))
                    } finally {
                      setBusy(false)
                    }
                  }}
                >
                  Refresh models
                </button>
                <button
                  disabled={busy}
                  onClick={async () => {
                    setBusy(true)
                    try {
                      await personalApi(`/model-connections/${connection.id}`, {
                        method: 'DELETE'
                      })
                      if (state.connectionId === connection.id)
                        state.select('', '')
                      await reload()
                      setNotice(
                        'Connection removed. Stored credentials were cleared.'
                      )
                    } catch (error) {
                      setNotice(String(error))
                    } finally {
                      setBusy(false)
                    }
                  }}
                >
                  Remove connection
                </button>
              </div>
            </article>
          ))}
          <p className="model-notice">
            Thinking controls are enabled only for supported provider/model
            combinations. Relay model names are provider-reported identifiers;
            availability is checked when you send. Uploaded documents remain
            unreviewed references.
          </p>
        </div>
      </DialogContent>
    </Dialog>
  )
}
