@echo off
chcp 65001 >nul
echo.
echo  正在启动 opencode 安装程序，请稍候...
echo.

:: 把自身内容（跳过前8行bat头）写到临时ps1文件，再用PowerShell执行
:: 这种方式比命令行内嵌更稳定，避免引号/换行转义问题
set TMPPS=%TEMP%\setup-opencode-tmp.ps1
powershell.exe -NoProfile -Command "Get-Content -LiteralPath '%~f0' -Encoding UTF8 | Select-Object -Skip 18 | Set-Content -Path '%TMPPS%' -Encoding UTF8"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%TMPPS%"

echo.
pause
del "%TMPPS%" >nul 2>&1
exit /b

#-- PowerShell 脚本内容从此行开始，请勿删除或修改以上内容 --#
#-- PowerShell 脚本内容从此行开始，请勿删除或修改以上内容 --#

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step { param($msg) Write-Host "`n[STEP] $msg" -ForegroundColor Cyan }
function Write-Ok   { param($msg) Write-Host "  [OK] $msg"   -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function Write-Fail { param($msg) Write-Host "  [FAIL] $msg" -ForegroundColor Red }

# =============================================================================
# STEP 1 — 检查运行环境（Node.js、Python、Git）
# =============================================================================
Write-Step "检查运行环境（Node.js、Python、Git）"

$envOk = $true

# -- 检查 Node.js --
$nodePath = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodePath) {
    Write-Fail "未检测到 Node.js！"
    Write-Host ""
    Write-Host "  ┌──────────────────────────────────────────────────────────────┐" -ForegroundColor Yellow
    Write-Host "  │  请安装 Node.js 后重新双击本脚本：                          │" -ForegroundColor Yellow
    Write-Host "  │                                                              │" -ForegroundColor Yellow
    Write-Host "  │  1. 打开 https://nodejs.org                                 │" -ForegroundColor Yellow
    Write-Host "  │  2. 点击 LTS 版本下载安装包                                 │" -ForegroundColor Yellow
    Write-Host "  │  3. 一路下一步完成安装（默认勾选添加 PATH）                 │" -ForegroundColor Yellow
    Write-Host "  │  4. 安装完成后重新双击本脚本                                │" -ForegroundColor Yellow
    Write-Host "  └──────────────────────────────────────────────────────────────┘" -ForegroundColor Yellow
    Write-Host ""
    $envOk = $false
} else {
    $nodeVersion = node --version
    $npmVersion  = npm --version
    Write-Ok "Node.js 已安装：$nodeVersion"
    Write-Ok "npm    已安装：v$npmVersion"
    $major = [int]($nodeVersion -replace 'v(\d+)\..*','$1')
    if ($major -lt 18) {
        Write-Warn "Node.js 版本 $nodeVersion 低于推荐的 v18，建议升级。"
    } else {
        Write-Ok "Node.js 版本满足要求（>= v18）"
    }
}

# -- 检查 Python --
$pythonCmd = $null
foreach ($cmd in @('python', 'python3')) {
    $c = Get-Command $cmd -ErrorAction SilentlyContinue
    if ($c) {
        # 确认是真正的 Python 而非 Windows Store 占位符
        $ver = & $cmd --version 2>&1
        if ($ver -match 'Python\s+3') {
            $pythonCmd = $cmd
            Write-Ok "Python 已安装：$ver"
            break
        }
    }
}
if (-not $pythonCmd) {
    Write-Fail "未检测到 Python 3！"
    Write-Host ""
    Write-Host "  ┌──────────────────────────────────────────────────────────────┐" -ForegroundColor Yellow
    Write-Host "  │  请安装 Python 3 后重新双击本脚本：                         │" -ForegroundColor Yellow
    Write-Host "  │                                                              │" -ForegroundColor Yellow
    Write-Host "  │  1. 打开 https://www.python.org/downloads                   │" -ForegroundColor Yellow
    Write-Host "  │  2. 点击 Download Python 3.x.x 下载安装包                  │" -ForegroundColor Yellow
    Write-Host "  │  3. 安装时务必勾选 "Add Python to PATH"                    │" -ForegroundColor Yellow
    Write-Host "  │  4. 安装完成后重新双击本脚本                                │" -ForegroundColor Yellow
    Write-Host "  └──────────────────────────────────────────────────────────────┘" -ForegroundColor Yellow
    Write-Host ""
    $envOk = $false
}

# -- 检查 Git --
$gitCmd = Get-Command git -ErrorAction SilentlyContinue
if (-not $gitCmd) {
    Write-Fail "未检测到 Git！"
    Write-Host ""
    Write-Host "  ┌──────────────────────────────────────────────────────────────┐" -ForegroundColor Yellow
    Write-Host "  │  请安装 Git 后重新双击本脚本：                              │" -ForegroundColor Yellow
    Write-Host "  │                                                              │" -ForegroundColor Yellow
    Write-Host "  │  1. 打开 https://git-scm.com/download/win                   │" -ForegroundColor Yellow
    Write-Host "  │  2. 下载并安装（一路下一步即可）                            │" -ForegroundColor Yellow
    Write-Host "  │  3. 安装完成后重新双击本脚本                                │" -ForegroundColor Yellow
    Write-Host "  └──────────────────────────────────────────────────────────────┘" -ForegroundColor Yellow
    Write-Host ""
    $envOk = $false
} else {
    Write-Ok "Git 已安装：$(git --version)"
}

if (-not $envOk) {
    Write-Host "  请安装以上缺失软件后重新双击运行本脚本。" -ForegroundColor Yellow
    exit 1
}

# =============================================================================
# STEP 2 — 配置用户级 PATH 环境变量（Node.js + npm 全局包路径）
# =============================================================================
Write-Step "配置用户级 PATH 环境变量"

$nodeBin   = Split-Path (Get-Command node).Source
$npmGlobal = Join-Path $env:APPDATA "npm"

$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if ($null -eq $userPath) { $userPath = '' }
$pathList = $userPath -split ';' | Where-Object { $_ -ne '' }

$changed = $false
foreach ($entry in @($nodeBin, $npmGlobal)) {
    if ($pathList -notcontains $entry) {
        $pathList += $entry
        $changed = $true
        Write-Ok "已添加到用户 PATH：$entry"
    } else {
        Write-Warn "已存在，跳过：$entry"
    }
}

if ($changed) {
    $newPath = ($pathList | Where-Object { $_ -ne '' }) -join ';'
    [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
    Write-Ok "用户 PATH 已更新（永久生效，重新打开 CMD 后可用）"
    $env:PATH = ($pathList -join ';') + ';' + $env:PATH
} else {
    Write-Warn "PATH 无需修改，路径均已存在"
}

# =============================================================================
# STEP 3 — 安装 opencode-ai
# =============================================================================
Write-Step "安装 opencode-ai（npm install -g opencode-ai）"

$opencodeCmd = Get-Command opencode -ErrorAction SilentlyContinue
if ($opencodeCmd) {
    Write-Warn "opencode 已安装，跳过（如需重装请手动运行 npm i -g opencode-ai）"
} else {
    try {
        npm i -g opencode-ai
        Write-Ok "opencode-ai 安装完成"
    } catch {
        Write-Fail "opencode-ai 安装失败：$($_.Exception.Message)"
        exit 1
    }
}

# =============================================================================
# STEP 4 — 克隆仓库并建立技能目录联接（Junction）
#
#   仓库完整克隆到：  %USERPROFILE%\.agents\sap-engineering-skill\
#   技能入口联接到：  %USERPROFILE%\.agents\skills\sap-adt-cli\
#              ↑ 指向仓库内 skills\sap-adt-cli\ 子目录
#
#   好处：
#     - 仓库与技能路径职责分离，结构清晰
#     - 更新时只需 git pull（在 .agents\sap-engineering-skill\ 执行），
#       技能链接自动反映最新代码，无需重新配置
# =============================================================================
Write-Step "克隆 sap-engineering-skill 仓库并配置技能目录联接"

$agentsDir = Join-Path $env:USERPROFILE ".agents"
$repoDir   = Join-Path $agentsDir "sap-engineering-skill"   # 完整仓库存放位置
$skillsDir = Join-Path $agentsDir "skills"                  # 技能根目录
$skillLink = Join-Path $skillsDir "sap-adt-cli"            # 技能入口（Junction）
$skillSrc  = Join-Path $repoDir   "skills\sap-adt-cli"     # 仓库内技能子目录

# 确保目录存在
foreach ($dir in @($agentsDir, $skillsDir)) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Ok "已创建目录：$dir"
    }
}

# 克隆仓库
if (Test-Path $repoDir) {
    Write-Warn "仓库已存在：$repoDir"
    Write-Warn "如需更新请进入该目录手动执行 git pull"
} else {
    try {
        git clone https://github.com/shrek-abaper/sap-engineering-skill "$repoDir"
        Write-Ok "克隆完成：$repoDir"
    } catch {
        Write-Fail "克隆失败：$($_.Exception.Message)"
        exit 1
    }
}

# 建立 Junction（目录联接），将技能子目录挂载到技能根目录
# Junction 无需管理员权限，行为等同于目录快捷方式
if (Test-Path $skillLink) {
    Write-Warn "技能链接已存在：$skillLink，跳过"
} else {
    try {
        New-Item -ItemType Junction -Path $skillLink -Target $skillSrc | Out-Null
        Write-Ok "技能链接创建完成"
        Write-Ok "  $skillLink"
        Write-Ok "  -> $skillSrc"
    } catch {
        Write-Fail "创建技能链接失败：$($_.Exception.Message)"
        exit 1
    }
}

# =============================================================================
# STEP 5 — 安装 Python 依赖
# =============================================================================
Write-Step "安装 Python 依赖（click、requests、urllib3）"

try {
    & $pythonCmd -m pip install --upgrade pip --quiet
    & $pythonCmd -m pip install click requests urllib3 --quiet
    Write-Ok "Python 依赖安装完成"
} catch {
    Write-Fail "Python 依赖安装失败：$($_.Exception.Message)"
    exit 1
}

# =============================================================================
# 完成摘要
# =============================================================================
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  ✔  全部安装完成！" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  Node.js      : $nodeVersion"
Write-Host "  npm          : v$npmVersion"
Write-Host "  Python       : $(& $pythonCmd --version)"
Write-Host "  仓库位置     : $repoDir"
Write-Host "  技能入口     : $skillLink"
Write-Host ""
Write-Host "  ─────────────────────────────────────────────────────────" -ForegroundColor Cyan
Write-Host "  🚀  如何启动 opencode" -ForegroundColor Cyan
Write-Host "  ─────────────────────────────────────────────────────────" -ForegroundColor Cyan
Write-Host ""
Write-Host "  步骤 1：参考官方文档配置 opencode.json" -ForegroundColor White
Write-Host "          https://opencode.ai/docs" -ForegroundColor Yellow
Write-Host ""
Write-Host "  步骤 2：打开 CMD（按 Win+R，输入 cmd，回车）" -ForegroundColor White
Write-Host ""
Write-Host "  步骤 3：输入以下命令启动 opencode：" -ForegroundColor White
Write-Host "          opencode" -ForegroundColor Yellow
Write-Host ""
Write-Host "  步骤 4：进入 opencode 后输入 /connect 连接模型提供商" -ForegroundColor White
Write-Host "          输入 API Key 后即可正常使用" -ForegroundColor Gray
Write-Host ""
Write-Host "  ─────────────────────────────────────────────────────────" -ForegroundColor Cyan
  Write-Host "  🔄  如何更新 sap-engineering-skill" -ForegroundColor Cyan
Write-Host "  ─────────────────────────────────────────────────────────" -ForegroundColor Cyan
Write-Host ""
Write-Host "  在以下目录执行 git pull 即可，技能自动生效：" -ForegroundColor White
Write-Host "  $repoDir" -ForegroundColor Yellow
Write-Host ""
Write-Host "  ─────────────────────────────────────────────────────────" -ForegroundColor Cyan
  Write-Host "  📖  sap-engineering-skill 使用文档" -ForegroundColor Cyan
Write-Host "  ─────────────────────────────────────────────────────────" -ForegroundColor Cyan
Write-Host ""
  Write-Host "          https://github.com/shrek-abaper/sap-engineering-skill" -ForegroundColor Yellow
Write-Host ""
Write-Host "  ─────────────────────────────────────────────────────────" -ForegroundColor Yellow
Write-Host "  💡  关于模型选择的建议" -ForegroundColor Yellow
Write-Host "  ─────────────────────────────────────────────────────────" -ForegroundColor Yellow
Write-Host ""
Write-Host "  opencode 提供免费模型，可直接上手体验。" -ForegroundColor White
Write-Host ""
Write-Host "  ⚠  ABAP 代码是企业核心资产，发送至公网模型存在数据合规" -ForegroundColor Yellow
Write-Host "     风险。如有顾虑，建议优先接入公司内网部署的模型底座。" -ForegroundColor Yellow
Write-Host ""
Write-Host "============================================================`n" -ForegroundColor Green
