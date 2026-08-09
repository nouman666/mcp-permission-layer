$paths = @(
  "c:\Users\as\Desktop\bodmas\CLEAN_FINAL_IEEE_PAPER_MCP.docx",
  "c:\Users\as\Desktop\bodmas\CLEAN_FINAL_IEEE_PAPER_MCP_MERGED_NEW.docx",
  "c:\Users\as\Desktop\CLEAN_FINAL_IEEE_PAPER_MCP_MERGED.docx"
)
$word = $null
try {
  $word = New-Object -ComObject Word.Application
  $word.Visible = $false
  foreach ($p in $paths) {
    if (-not (Test-Path $p)) { Write-Output "MISSING $p"; continue }
    $doc = $word.Documents.Open($p, $false, $true)
    $doc.Repaginate()
    Start-Sleep -Milliseconds 500
    $pages = $doc.ComputeStatistics(2)
    $words = $doc.ComputeStatistics(0)
    $name = [IO.Path]::GetFileName($p)
    Write-Output "${name}: pages=$pages words=$words"
    $doc.Close($false) | Out-Null
  }
} catch {
  Write-Output "COM_FAIL: $($_.Exception.Message)"
} finally {
  if ($word -ne $null) {
    $word.Quit() | Out-Null
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
  }
}
