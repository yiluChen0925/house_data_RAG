# 项目自检脚本（给 AI 助手/人工使用，一条命令跑完，不需要 heredoc）
#
# 为什么单独做成脚本：
#   1) huggingface_hub 的离线开关是导入时冻结的常量，必须在【进程启动前】用环境变量设好，
#      在脚本里写 os.environ 可能来不及。本脚本在启动 python 之前就把变量设好，这是唯一
#      不依赖导入顺序的保证（否则会去连 huggingface.co 并超时重试 5 次，长达十几分钟）。
#   2) 把检查项固定下来，避免每次临时拼命令。
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File 2_scripts\selfcheck.ps1

$ErrorActionPreference = 'Continue'
# 兼容两种调用方式：-File 执行，或 Get-Content | Invoke-Expression（后者没有 $MyInvocation.MyCommand.Path）
$scriptPath = $MyInvocation.MyCommand.Path
if ([string]::IsNullOrEmpty($scriptPath)) { $scriptPath = $PSCommandPath }
if ([string]::IsNullOrEmpty($scriptPath)) {
    $root = (Get-Location).Path
} else {
    $here = Split-Path -Parent $scriptPath
    $root = Split-Path -Parent $here
}
Set-Location $root

Write-Host "project root: $root"
$fail = 0
$sw = [Diagnostics.Stopwatch]::StartNew()

# ---- 1) force offline BEFORE any python process starts ----
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:HF_HUB_DISABLE_PROGRESS_BARS = '1'
$env:TOKENIZERS_PARALLELISM = 'false'
$env:PYTHONIOENCODING = 'utf-8'

function Check($name, $ok, $detail) {
    if ($ok) { Write-Host ("[PASS] " + $name + "  " + $detail) }
    else { Write-Host ("[FAIL] " + $name + "  " + $detail); $script:fail++ }
}

# ---- 2) offline flag really in effect ----
$off = (python -c "from huggingface_hub import constants; print(constants.HF_HUB_OFFLINE)" 2>&1 | Select-Object -Last 1)
Check "offline flag" ($off -eq 'True') ("HF_HUB_OFFLINE = " + $off)

# ---- 3) cleaned csv row count ----
$rows = (python -c "import pandas as pd; df=pd.read_csv(r'1_data/cleaned_data/house_cleaned.csv',encoding='utf-8-sig'); print(len(df))" 2>&1 | Select-Object -Last 1)
Check "cleaned csv rows" ($rows -eq '15067') ("rows = " + $rows)

# ---- 4) vector store count ----
$vec = (python -c "import chromadb; c=chromadb.PersistentClient(path=r'1_data/chroma_db'); print([(x.name,x.count()) for x in c.list_collections()])" 2>&1 | Select-Object -Last 1)
Check "vector store" ($vec -match '15063') ("collections = " + $vec)

# ---- 5) retrieval end to end (3 queries, no LLM call, no cost) ----
$log = Join-Path $env:TEMP 'selfcheck_retriever.log'
python -X utf8 "2_scripts\rag\hybrid_retriever.py" > $log 2>&1
$code = $LASTEXITCODE
$hits = (Select-String -Path $log -Pattern '^\d+\. ' -ErrorAction SilentlyContinue | Measure-Object).Count
Check "retrieval 9 rows" ($hits -ge 9) ("matched lines = $hits, exit = $code")
if ($code -ne 0) {
    Write-Host "[WARN] retriever exit code $code ; last output:"
    Get-Content $log -Tail 5 | ForEach-Object { Write-Host ("    " + $_) }
}

$sw.Stop()
Write-Host ("elapsed: " + [math]::Round($sw.Elapsed.TotalSeconds, 1) + "s")
if ($fail -eq 0) {
    Write-Host ""
    Write-Host "ALL CHECKS PASSED"
    # machine-readable sentinel: the last line always marks completion, so a caller
    # can decide success/failure from a single read instead of polling the file.
    Write-Host "SELFCHECK_DONE exit=0"
    exit 0
} else {
    Write-Host ""
    Write-Host ("FAILED CHECKS: " + $fail)
    Write-Host "SELFCHECK_DONE exit=1"
    exit 1
}
