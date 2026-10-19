import { test } from 'node:test'
import assert from 'node:assert/strict'
import { reportIdFromTools, chartNumbers, reportPresentation, formatReportValue } from '../src/lib/report-artifact.ts'
import { readMarketStream } from '../src/lib/market-stream.ts'

test('native report IDs come only from successful evidence tool results, including replay JSON', () => {
  assert.equal(reportIdFromTools([{tool_name:'search_market_evidence',result:'{"report_id":"saved-1"}'}]),'saved-1')
  assert.equal(reportIdFromTools([{tool_name:'untrusted',result:{report_id:'forged'}}]),undefined)
  assert.equal(reportIdFromTools([{tool_name:'search_market_evidence',tool_call_error:true,result:{report_id:'failed'}}]),undefined)
  assert.equal(reportIdFromTools([{tool_name:'search_market_evidence',result:'invalid'}]),undefined)
})

test('quantitative charts reject missing and non-finite values', () => {
  assert.deepEqual(chartNumbers({points:[{value:'8'},{value:'7.25'}]}),[8,7.25])
  for (const value of [null,undefined,'','Infinity','bad']) assert.equal(chartNumbers({points:[{value}]}),null)
  assert.equal(chartNumbers({points:[]}),null)
})

test('report presentation preserves conflicting observations and geography boundaries', () => {
  const report={geographies:['City','West End','Canary Wharf'],scope:{metrics:['rent','vacancy']},
    market_snapshot:[{fact_id:'a',geography:'West End',metric:'vacancy',value:'6.7',review_status:'pending_review'},
      {fact_id:'b',geography:'West End',metric:'vacancy',value:'7.5',review_status:'pending_review'},
      {fact_id:'c',geography:'City (publisher definition)',metric:'rent',value:'95',review_status:'pending_review'},
      {fact_id:'d',geography:'Canary Wharf & Docklands',metric:'vacancy',value:'9.7',review_status:'pending_review'}],
    charts:[{status:'unavailable'},{status:'ready'}],data_gaps:[{geography:'City',metric:'rent'},{geography:'City',metric:'rent',component:'history'}]}
  const view=reportPresentation(report)
  assert.equal(view.regions[1].cells[1].observations.length,2)
  assert.equal(view.regions[2].cells[1].observations.length,0)
  assert.equal(view.regions[0].cells[0].observations[0].fact_id,'c')
  assert.equal(view.coveredCells,2)
  assert.equal(view.totalCells,6)
  assert.equal(view.readyCharts.length,1)
  assert.equal(view.gapGroups[0].current.length,1)
  assert.equal(view.gapGroups[0].history.length,1)
  assert.equal(report.market_snapshot[0].review_status,'pending_review')
})

test('report typography preserves source numeric precision', () => {
  assert.equal(formatReportValue('95.00'),'95.00')
  assert.equal(formatReportValue('1000000.0'),'1,000,000.0')
  assert.equal(formatReportValue('1.0'),'1.0')
  assert.equal(formatReportValue('not stated'),'not stated')
})

test('progress and report events are delivered before completion across byte boundaries', async () => {
  const events=[]
  const text=[{type:'progress',stage:'evidence',message:'Checking sources'},{type:'report',report_id:'r',report:{report_id:'r',title:'£ London'}},{type:'done',report_id:'r'}].map(e=>'data: '+JSON.stringify(e)+'\r\n\r\n').join('')
  const body=new ReadableStream({start(c){for(const b of new TextEncoder().encode(text))c.enqueue(Uint8Array.of(b));c.close()}})
  await readMarketStream(body,e=>events.push(e))
  assert.deepEqual(events.map(e=>e.type),['progress','report','done'])
  assert.equal(events[1].report.title,'£ London')
})
