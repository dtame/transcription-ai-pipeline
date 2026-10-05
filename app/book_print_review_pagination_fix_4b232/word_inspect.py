"""Inspect finalized Word pages for chapter transitions and front matter."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from app.book_print_review_pagination_fix_4b232.constants import PHASE
from app.book_print_review_pagination_fix_4b232.guard import BookPrintReviewPaginationFix4232Error
from app.word_renderer.finalizer import powershell_available, word_progid_present


_POWERSHELL_SCRIPT = r"""
param(
    [Parameter(Mandatory = $true)][string]$InputDocx,
    [Parameter(Mandatory = $true)][string]$ReportJson
)

$ErrorActionPreference = "Stop"
$report = [ordered]@{
    ok = $false
    status = "FAIL"
    page_count = 0
    chapters = @()
    pages = @()
    front_matter_pages = @()
    error = ""
}

function Write-Report {
    ($report | ConvertTo-Json -Compress -Depth 8) | Set-Content -LiteralPath $ReportJson -Encoding utf8
}

function Page-Text($document, [int]$page, [int]$total) {
    $start = $document.GoTo(1, 1, $page)
    if ($page -lt $total) {
        $end = $document.GoTo(1, 1, $page + 1)
        $range = $document.Range($start.Start, $end.Start)
    } else {
        $range = $document.Range($start.Start, $document.Content.End)
    }
    return ($range.Text -replace "[\r\a]", "")
}

$word = $null
$doc = $null
$createdNew = $false
try {
    $beforePids = @(Get-Process -Name WINWORD -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
    $word = New-Object -ComObject Word.Application
    Start-Sleep -Milliseconds 400
    $afterPids = @(Get-Process -Name WINWORD -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
    $createdNew = @($afterPids | Where-Object { $beforePids -notcontains $_ }).Count -gt 0
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $resolved = (Resolve-Path -LiteralPath $InputDocx).Path
    $doc = $word.Documents.Open($resolved, $false, $true, $false)
    $doc.Repaginate()
    $total = [int]$doc.ComputeStatistics(2)
    $report.page_count = $total

    $chapters = @()
    foreach ($para in $doc.Paragraphs) {
        $style = $null
        try { $style = [string]$para.Style.NameLocal } catch { continue }
        if ($style -eq "BookChapterTitle") {
            $title = ($para.Range.Text -replace "[\r\a]", "").Trim()
            $page = [int]$para.Range.Information(3)
            $adjusted = $page
            try { $adjusted = [int]$para.Range.Information(1) } catch {}
            $chapters += [ordered]@{
                title = $title
                first_page = $page
                last_page = $page
                page_adjusted = $adjusted
            }
        }
    }
    for ($i = 0; $i -lt $chapters.Count; $i++) {
        if ($i -lt $chapters.Count - 1) {
            $chapters[$i].last_page = [int]$chapters[$i + 1].first_page - 1
        } else {
            $chapters[$i].last_page = $total
        }
    }
    $report.chapters = $chapters

    $pages = @()
    for ($p = 1; $p -le $total; $p++) {
        $text = Page-Text $doc $p $total
        $plain = ($text -replace "[\s\u000c\u0007]", "")
        $trimmed = $text.Trim()
        $preview = ""
        if ($trimmed.Length -gt 0) {
            $preview = $trimmed.Substring(0, [Math]::Min(2000, $trimmed.Length))
        }
        $pages += [ordered]@{
            page = $p
            text_length = $plain.Length
            preview = $preview
            blank = ($plain.Length -eq 0)
        }
    }
    $report.pages = $pages
    $firstChapter = 1
    if ($chapters.Count -gt 0) { $firstChapter = [int]$chapters[0].first_page }
    $report.front_matter_pages = @($pages | Where-Object { $_.page -lt $firstChapter })
    $report.ok = $true
    $report.status = "PASS"
}
catch {
    $report.error = [string]$_.Exception.Message
    $report.status = "FAIL"
    $report.ok = $false
}
finally {
    if ($null -ne $doc) {
        try { $doc.Close($false) | Out-Null } catch {}
        try { [System.Runtime.InteropServices.Marshal]::ReleaseComObject($doc) | Out-Null } catch {}
    }
    if ($null -ne $word) {
        if ($createdNew) {
            try { $word.Quit() | Out-Null } catch {}
        }
        try { [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null } catch {}
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
    Write-Report
}

if (-not $report.ok) { exit 1 }
exit 0
"""


def inspect_word_document(path: Path) -> dict[str, Any]:
    target = Path(path)
    if not target.is_file():
        return {
            "phase": PHASE,
            "status": "NOT_AVAILABLE",
            "error": f"DOCX missing: {target}",
            "pages": [],
            "chapters": [],
        }
    if not (word_progid_present() and powershell_available()):
        return {
            "phase": PHASE,
            "status": "NOT_AVAILABLE",
            "error": "Microsoft Word is not available for page inspection.",
            "pages": [],
            "chapters": [],
        }
    with tempfile.TemporaryDirectory(prefix="word-inspect-4b232-") as tmp:
        script = Path(tmp) / "inspect.ps1"
        report = Path(tmp) / "inspect.json"
        local = Path(tmp) / "inspect.docx"
        shutil.copy2(target.resolve(), local)
        script.write_text(_POWERSHELL_SCRIPT, encoding="utf-8")
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
                "-InputDocx",
                str(local.resolve()),
                "-ReportJson",
                str(report.resolve()),
            ],
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        payload: dict[str, Any] = {}
        if report.is_file():
            raw = report.read_text(encoding="utf-8-sig")
            payload = json.loads(raw) if raw.strip() else {}
        if completed.returncode != 0 and not payload:
            raise BookPrintReviewPaginationFix4232Error(
                "Word page inspection failed: "
                + ((completed.stderr or completed.stdout or "unknown error").strip())
            )
        payload["phase"] = PHASE
        payload["path"] = str(target).replace("\\", "/")
        payload["returncode"] = completed.returncode
        if not payload.get("status"):
            payload["status"] = "FAIL" if completed.returncode else "PASS"
        return payload


__all__ = ["inspect_word_document"]
