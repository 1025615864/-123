param(
  [Parameter(Mandatory = $true)][string]$BaseUrl,
  [Parameter(Mandatory = $true)][string]$AdminToken,
  [Parameter(Mandatory = $false)][int]$PollSeconds = 30,
  [Parameter(Mandatory = $false)][int]$IntervalSeconds = 1,
  [Parameter(Mandatory = $false)][switch]$Strict
)

$ErrorActionPreference = "Stop"

function Normalize-BaseUrl([string]$Url) {
  $u = ($Url ?? "").Trim()
  if ($u.EndsWith("/")) {
    return $u.TrimEnd("/")
  }
  return $u
}

function Invoke-Json([string]$Method, [string]$Url, $Body = $null) {
  $headers = @{ "Authorization" = "Bearer $AdminToken" }
  if ($null -ne $Body) {
    return Invoke-RestMethod -Method $Method -Uri $Url -Headers $headers -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 20)
  }
  return Invoke-RestMethod -Method $Method -Uri $Url -Headers $headers
}

$BaseUrl = Normalize-BaseUrl $BaseUrl

Write-Host "[1/7] Health check..."
Invoke-RestMethod -Method GET -Uri "$BaseUrl/health" | Out-Null
Invoke-RestMethod -Method GET -Uri "$BaseUrl/api/health" | Out-Null

Write-Host "[2/7] News AI status (admin)..."
$st = Invoke-Json GET "$BaseUrl/api/system/news-ai/status"
if ($null -eq $st) { throw "news-ai status is null" }

Write-Host "[3/7] Create a test news (admin)..."
$now = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$title = "SMOKE-NEWS-AI-$now"
$payload = @{
  title = $title
  category = "general"
  summary = $null
  cover_image = $null
  source = "SMOKE"
  author = "SMOKE"
  content = "Smoke test content $now"
  is_top = $false
  is_published = $true
  review_status = "approved"
}

$news = Invoke-Json POST "$BaseUrl/api/news" $payload
$newsId = [int]$news.id
if ($newsId -le 0) { throw "invalid newsId" }

try {
  Write-Host "[4/7] Trigger AI rerun..."
  Invoke-Json POST "$BaseUrl/api/news/admin/$newsId/ai/rerun" | Out-Null

  Write-Host "[5/7] Poll admin detail until ai_annotation.processed_at is set..."
  $deadline = (Get-Date).AddSeconds([double]$PollSeconds)
  $ok = $false
  while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds $IntervalSeconds

    $detail = Invoke-Json GET "$BaseUrl/api/news/admin/$newsId"
    $ann = $detail.ai_annotation
    if ($null -eq $ann) { continue }

    $processedAt = $ann.processed_at
    if ($null -eq $processedAt -or $processedAt.ToString().Trim().Length -eq 0) {
      continue
    }

    if ($Strict) {
      $highlights = $ann.highlights
      $keywords = $ann.keywords
      $hlOk = ($null -ne $highlights -and $highlights.Count -gt 0)
      $kwOk = ($null -ne $keywords -and $keywords.Count -gt 0)
      if (-not ($hlOk -and $kwOk)) {
        continue
      }
    }

    $ok = $true
    break
  }

  if (-not $ok) {
    throw "AI annotation not ready in time (PollSeconds=$PollSeconds, Strict=$($Strict.IsPresent))"
  }

  Write-Host "[6/7] OK: AI rerun succeeded."
} finally {
  Write-Host "[7/7] Cleanup: delete test news..."
  try {
    Invoke-Json DELETE "$BaseUrl/api/news/$newsId" | Out-Null
  } catch {
    Write-Host "Cleanup failed: $($_.Exception.Message)"
  }
}

Write-Host "DONE"
