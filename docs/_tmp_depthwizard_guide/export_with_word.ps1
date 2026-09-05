$ErrorActionPreference = 'Stop'

$docxPath = (Resolve-Path -LiteralPath '..\output\DepthWizard_Team_Technical_and_Judge_Guide.docx').Path
$repositoryRoot = (Resolve-Path -LiteralPath '..\..').Path
$pdfDirectory = Join-Path $repositoryRoot 'output\pdf'
New-Item -ItemType Directory -Path $pdfDirectory -Force | Out-Null
$pdfPath = Join-Path $pdfDirectory 'DepthWizard_Team_Technical_and_Judge_Guide.pdf'

$word = $null
$document = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $document = $word.Documents.Open($docxPath, $false, $false)

    for ($pass = 0; $pass -lt 2; $pass++) {
        foreach ($toc in $document.TablesOfContents) {
            $toc.Update() | Out-Null
        }
        $document.Fields.Update() | Out-Null
        foreach ($section in $document.Sections) {
            foreach ($footer in $section.Footers) {
                $footer.Range.Fields.Update() | Out-Null
            }
        }
        $document.Repaginate()
    }

    $pageCount = $document.ComputeStatistics(2)
    Write-Output "Laid out pages: $pageCount"
    $document.Save()
    # wdFormatPDF=17. SaveAs2 is more reliable than the fixed-format call on
    # this local Word build for long, image-rich reports.
    $document.SaveAs2($pdfPath, 17)
    Write-Output $pdfPath
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
