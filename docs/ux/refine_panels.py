"""One-time, bounded extraction of the existing comparison panel; preserves its API calls."""
from pathlib import Path

path = Path(__file__).parents[2] / 'app/frontend/src/components/market/MarketApp.tsx'
source = path.read_text(encoding='utf-8')
start = source.index('function EventsPage(')
end = source.index('\nfunction SourceHealth(', start)
events = source[start:end]
state_start = events.index("  const comparisons = useMarket")
state_end = events.index('  return (', state_start)
states = events[state_start:state_end].replace("useState(''),\n    [newId", "useState(initialId),\n    [newId")
panel_start = events.index('      <Panel\n        title="Period comparisons"')
panel_end = events.index('      <Stamp updated={state.updated}', panel_start)
panel = events[panel_start:panel_end]
events = events[:panel_start] + '      <ComparisonsPanel act={act} busy={busy} notify={notify} />\n' + events[panel_end:]
events = events[:state_start] + events[state_end:]
component = '''
function ComparisonsPanel({ act, busy, notify, initialId = '' }: { act: Action; busy: string | null; notify: (value: string) => void; initialId?: string }) {
''' + states + '''  useEffect(() => { if (initialId) setOldId(initialId) }, [initialId])
  return (
    <section id="comparison" aria-label="Compare saved observations">
''' + panel + '''    </section>
  )
}
'''
source = source[:start] + events + component + source[end:]
data_start = source.index('function DataPage(')
data_end = source.index('\nfunction EventList(', data_start)
data = source[data_start:data_end]
marker = '      <Panel\n        title="Source document archive"'
assert marker in data
data = data.replace(marker, '''      <details open={Boolean(filters.get('compare'))} className="rounded-xl border border-slate-200 bg-white p-4">
        <summary className="cursor-pointer text-sm font-semibold">Compare saved observations</summary>
        <p className="my-3 text-sm text-slate-600">The service checks review status, definitions, geography and units. Unreviewed inputs remain blocked; opening this panel does not approve data.</p>
        <ComparisonsPanel act={act} busy={busy} notify={notify} initialId={filters.get('compare') || ''} />
      </details>
''' + marker, 1)
source = source[:data_start] + data + source[data_end:]
source = source.replace('No eligible comparisons yet. Review evidence before validating\n            observations.', 'No comparison checks recorded yet. Inspect evidence first; this interface does not approve observations.')
path.write_text(source, encoding='utf-8')
print('Existing comparison panel reused in Events and Market Data')
