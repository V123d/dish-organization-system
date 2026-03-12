@echo off
chcp 65001 >nul
echo.
echo ============================================
echo   走云智能排菜系统 — 一键启动脚本
echo ============================================
echo.

REM 检查 .env 文件
if not exist "backend\.env" (
    echo [警告] 未找到 backend\.env 文件
    echo 正在从 .env.example 创建...
    copy "backend\.env.example" "backend\.env" >nul
    echo.
    echo ⚠️  请先编辑 backend\.env 文件，填入您的 LLM API Key：
    echo    打开文件：backend\.env
    echo    修改行：  LLM_API_KEY=sk-your-api-key-here
    echo.
    pause
    exit /b 1
)

REM 检查 API Key 是否已配置
findstr /C:"sk-your-api-key-here" "backend\.env" >nul 2>&1
if %errorlevel% equ 0 (
    echo ⚠️  检测到 API Key 未配置！
    echo    请编辑 backend\.env 文件，将 LLM_API_KEY 替换为您的真实 API Key
    echo.
    pause
    exit /b 1
)

echo [1/4] 安装后端依赖...
cd backend
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple -q
cd ..

echo [2/4] 安装前端依赖...
cd frontend
call npm install --silent 2>nul
cd ..

echo [3/4] 启动后端服务 (端口 8000)...
start "走云后端" cmd /c "cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

echo [4/4] 启动前端服务 (端口 5173)...
timeout /t 2 /nobreak >nul
start "走云前端" cmd /c "cd frontend && npm run dev"

echo.
echo ✅ 启动完成！
echo    前端地址: http://localhost:5173
echo    后端地址: http://localhost:8000
echo    API 文档: http://localhost:8000/docs
echo    智能体注册表: http://localhost:8000/api/agents
echo.
echo 提示：关闭此窗口不会停止服务，需手动关闭"走云后端"和"走云前端"窗口。
pause
