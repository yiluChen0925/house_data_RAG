# 项目自检脚本：一条命令检查环境与数据是否就绪
#
# 检查四项：离线开关是否生效、清洗数据行数、向量库条数、检索链路是否通。
# 全部通过时打印 ALL CHECKS PASSED 并以退出码 0 结束，可直接用于 CI 或手动验收。
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File 2_scripts\selfcheck.ps1
#
# 关于离线：huggingface_hub 的离线开关是模块导入时求值的常量，所以必须在启动 python
# 之前用环境变量设好（在 python 里再写 os.environ 可能已经晚了，库会去连网并超时重试）。

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

# ---- 1) 在启动任何 python 进程之前设好离线开关 ----
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:HF_HUB_DISABLE_PROGRESS_BARS = '1'
$env:TOKENIZERS_PARALLELISM = 'false'
$env:PYTHONIOENCODING = 'utf-8'

function Check($name, $ok, $detail) {
    if ($ok) { Write-Host ("[PASS] " + $name + "  " + $detail) }
    else { Write-Host ("[FAIL] " + $name + "  " + $detail); $script:fail++ }
}

# ---- 2) 确认离线开关真的生效 ----
$off = (python -c "from huggingface_hub import constants; print(constants.HF_HUB_OFFLINE)" 2>&1 | Select-Object -Last 1)
Check "offline flag" ($off -eq 'True') ("HF_HUB_OFFLINE = " + $off)

# ---- 3) 清洗后数据行数 ----
$rows = (python -c "import pandas as pd; df=pd.read_csv(r'1_data/cleaned_data/house_cleaned.csv',encoding='utf-8-sig'); print(len(df))" 2>&1 | Select-Object -Last 1)
Check "cleaned csv rows" ($rows -eq '15067') ("rows = " + $rows)

# ---- 4) 向量库条数 ----
$vec = (python -c "import chromadb; c=chromadb.PersistentClient(path=r'1_data/chroma_db'); print([(x.name,x.count()) for x in c.list_collections()])" 2>&1 | Select-Object -Last 1)
Check "vector store" ($vec -match '15063') ("collections = " + $vec)

# ---- 5) 检索链路端到端（3 个查询，不调大模型、不产生费用）----
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
    exit 0
} else {
    Write-Host ""
    Write-Host ("FAILED CHECKS: " + $fail)
    exit 1
}
