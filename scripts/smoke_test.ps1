param([int]$BackendPort=8000)
$ErrorActionPreference='Stop'
$base="http://127.0.0.1:$BackendPort"
$health=Invoke-RestMethod "$base/health" -TimeoutSec 15
if($health.status -ne 'ok' -or $health.mode -ne 'mock' -or !$health.PSObject.Properties['data_asof'] -or !$health.PSObject.Properties['sources'] -or !$health.disclaimer){throw 'Health contract failed'}
$skills=Invoke-RestMethod "$base/skills" -TimeoutSec 15
if(!$skills.skills -or !$skills.PSObject.Properties['sources'] -or !$skills.disclaimer){throw 'Skills contract failed'}
$chat=Invoke-RestMethod "$base/chat" -Method Post -ContentType 'application/json' -Body '{"message":"What is the latest saved West End prime rent?","session_id":"smoke"}' -TimeoutSec 30
if(!$chat.answer -or !$chat.PSObject.Properties['sources'] -or !$chat.PSObject.Properties['as_of'] -or !$chat.skill_calls -or !$chat.disclaimer){throw 'Chat contract failed'}
$report=Invoke-RestMethod "$base/report" -Method Post -ContentType 'application/json' -Body '{}' -TimeoutSec 30
if(!$report.markdown -or !$report.PSObject.Properties['sources'] -or !$report.disclaimer){throw 'Report contract failed'}
$alerts=Invoke-RestMethod "$base/alerts" -TimeoutSec 15
if(!$alerts.settings -or !$alerts.PSObject.Properties['sources'] -or !$alerts.disclaimer){throw 'Alerts contract failed'}
Write-Output "PASS health skills chat report alerts; chat_sources=$($chat.sources.Count); report_sources=$($report.sources.Count); data_asof=$($health.data_asof)"
