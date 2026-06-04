# =============================================================================
# AI 智能记账系统 — PowerShell 上传脚本
# =============================================================================
# 用法: 右键 → 使用 PowerShell 运行
#        或在 PowerShell 中执行: .\upload.ps1
# =============================================================================

$ErrorActionPreference = "Stop"

$SERVER = "root@8.210.26.225"
$REMOTE_DIR = "/opt/ledgerai"
$PROJECT_DIR = $PSScriptRoot

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  AI 智能记账系统 — 上传到服务器" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: 创建远程目录
Write-Host "[1/4] 在服务器创建目录..." -ForegroundColor Yellow
ssh $SERVER "mkdir -p $REMOTE_DIR"

# Step 2: 打包项目（排除不需要的文件）
Write-Host "[2/4] 打包项目文件..." -ForegroundColor Yellow
$tarFile = "$PROJECT_DIR\ledgerai-deploy.tar.gz"
# 使用 git archive 或 tar（Windows 10+ 自带 tar）
Push-Location $PROJECT_DIR
tar --exclude='node_modules' --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='oh-my-claudecode' --exclude='venv' --exclude='.venv' -czf $tarFile .
Pop-Location
Write-Host "  打包完成: $tarFile" -ForegroundColor Green

# Step 3: 上传到服务器
Write-Host "[3/4] 上传到服务器（约 1-3 分钟）..." -ForegroundColor Yellow
scp $tarFile "${SERVER}:${REMOTE_DIR}/ledgerai-deploy.tar.gz"

# Step 4: 解压并设置权限
Write-Host "[4/4] 解压并设置权限..." -ForegroundColor Yellow
ssh $SERVER @"
mkdir -p ${REMOTE_DIR}/ai-accounting-system
cd ${REMOTE_DIR}/ai-accounting-system
tar -xzf ../ledgerai-deploy.tar.gz
rm ../ledgerai-deploy.tar.gz
chmod +x deploy.sh
"@

# 清理本地临时文件
Remove-Item $tarFile -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  上传完成！" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "接下来在服务器执行:" -ForegroundColor Cyan
Write-Host "  ssh $SERVER"
Write-Host "  cd $REMOTE_DIR/ai-accounting-system"
Write-Host "  nano .env.production    # 填写 ★★★ 标记的字段"
Write-Host "  bash deploy.sh"
Write-Host ""
Write-Host "按任意键退出..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
