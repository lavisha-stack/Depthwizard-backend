$ErrorActionPreference = 'Stop'

$docxPath = (Resolve-Path -LiteralPath '..\output\DepthWizard_Team_Technical_and_Judge_Guide.docx').Path
$chunkDirectory = Join-Path (Get-Location) 'pdf-chunks'
New-Item -ItemType Directory -Path $chunkDirectory -Force | Out-Null

$word = $null
$document = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $document = $word.Documents.Open($docxPath, $false, $true)
    $pageCount = $document.ComputeStatistics(2)
    Write-Output "Laid out pages: $pageCount"

    $chunkSize = 5
    for ($from = 1; $from -le $pageCount; $from += $chunkSize) {
        $to = [Math]::Min($pageCount, $from + $chunkSize - 1)
        $chunkPath = Join-Path $chunkDirectory ("pages-{0:D3}-{1:D3}.pdf" -f $from, $to)
        Write-Output "Exporting pages $from-$to"
        # wdExportFromTo=3, wdExportDocumentContent=0, no per-chunk bookmarks.
        $document.ExportAsFixedFormat($chunkPath, 17, $false, 0, 3, $from, $to, 0, $true, $true, 0, $true, $true, $false)
        Write-Output "Completed pages $from-$to"
    }
}
finally {
    if ($document -ne $null) {
        $document.Close($false)
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($document) | Out-Null
    }
    if ($word -ne $null) {
        $word.Quit()
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
