'use client'
import { useState } from 'react'

export default function CoveragePicker({
  label,
  selected,
  options,
  onChange
}: {
  label: string
  selected: string[]
  options: string[]
  onChange: (values: string[]) => void
}) {
  const [query, setQuery] = useState('')
  const values = Array.from(new Set([...selected, ...options])).filter(Boolean)
  const name = (value: string) =>
    (
      ({
        takeup: 'Take-up',
        interest_rate: 'Interest rate',
        vacancy: 'Vacancy',
        rent: 'Rent',
        supply: 'Supply',
        employment: 'Employment'
      }) as Record<string, string>
    )[value] || value.replaceAll('_', ' ')
  const visible = values.filter((value) =>
    name(value).toLowerCase().includes(query.toLowerCase())
  )
  return (
    <fieldset className="min-w-0 rounded-lg border border-slate-200 p-4">
      <legend className="px-2 text-sm font-medium">{label}</legend>
      <input
        className="mb-3 h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900"
        aria-label={`Search ${label.toLowerCase()} options`}
        placeholder={`Search ${label.toLowerCase()}`}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <div className="max-h-44 space-y-2 overflow-y-auto">
        {visible.map((value) => (
          <label key={value} className="flex items-start gap-2 text-sm">
            <input
              className="mt-1"
              type="checkbox"
              checked={selected.includes(value)}
              onChange={(e) =>
                onChange(
                  e.target.checked
                    ? [...selected, value]
                    : selected.filter((item) => item !== value)
                )
              }
            />
            <span>{name(value)}</span>
          </label>
        ))}
      </div>
      {!visible.length && <p className="text-sm">No matching saved options.</p>}
      <p className="mt-3 text-xs text-slate-600">
        {selected.length} selected. Choices come from saved settings and source
        records. Saved values are retained even if absent from the current
        source list.
      </p>
      {!selected.length && (
        <p role="alert" className="mt-2 text-sm text-red-800">
          Select at least one option before saving.
        </p>
      )}
    </fieldset>
  )
}
