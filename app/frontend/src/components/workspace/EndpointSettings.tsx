'use client'
import { useEffect, useState } from 'react'

/** Application-service URL only. Provider credentials belong in Models & API keys. */
export function saveEndpoint(
  value: string,
  onSave: (value: string) => void
): boolean {
  try {
    const url = new URL(value.trim())
    if (
      !['http:', 'https:'].includes(url.protocol) ||
      url.username ||
      url.password ||
      url.search ||
      url.hash
    )
      return false
    onSave(url.toString().replace(/\/+$/, ''))
    return true
  } catch {
    return false
  }
}

export default function EndpointSettings({
  endpoint,
  onSave,
  disabled = false
}: {
  endpoint: string
  onSave: (endpoint: string) => void
  disabled?: boolean
}) {
  const [value, setValue] = useState(endpoint)
  const [error, setError] = useState('')
  useEffect(() => {
    setValue(endpoint)
    setError('')
  }, [endpoint])
  return (
    <form
      className="my-3 space-y-2"
      onSubmit={(event) => {
        event.preventDefault()
        if (disabled) return
        setError(
          saveEndpoint(value, onSave)
            ? ''
            : 'Use an HTTP or HTTPS application-service URL without credentials, query parameters or fragments.'
        )
      }}
    >
      <label htmlFor="agentos-endpoint">AgentOS endpoint</label>
      <input
        id="agentos-endpoint"
        type="url"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        disabled={disabled}
        required
        className="w-full rounded-lg border bg-transparent p-2 text-sm"
        spellCheck={false}
      />
      <button
        type="submit"
        disabled={disabled}
        className="min-h-10 rounded-lg border px-3 py-2"
      >
        Save connection
      </button>
      {error && <p role="alert">{error}</p>}
      <p>
        This connects the website to its application service. Configure your
        model provider and key in Models &amp; API keys.
      </p>
    </form>
  )
}
