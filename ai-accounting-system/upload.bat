@echo off
chcp 65001 >nul
echo.
echo ==========================================
echo   AI 智能记账系统 — 上传到服务器
echo ==========================================
echo.

set SERVER=root@8.210.26.225
set REMOTE_DIR=/opt/ledgerai
set PROJECT_DIR=%~dp0

echo [1/3] 在服务器创建目录...
ssh %SERVER% "mkdir -p %REMOTE_DIR%"

echo [2/3] 上传项目文件（约 2-5 分钟）...
scp -r "%PROJECT_DIR%." %SERVER%:%REMOTE_DIR%/ai-accounting-system/

echo [3/3] 设置脚本权限...
ssh %SERVER% "chmod +x %REMOTE_DIR%/ai-accounting-system/deploy.sh"

echo.
echo ==========================================
echo   上传完成！
echo ==========================================
echo.
echo 接下来在服务器执行:
echo   ssh %SERVER%
echo   cd %REMOTE_DIR%/ai-accounting-system
echo   nano .env.production    # 填写 ★★★ 标记的字段
echo   bash deploy.sh
echo.
pause
