@echo off
echo ========================================
echo   AutoTube Publisher - GitHub Setup
echo ========================================

:: Check if git is installed
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Git nao encontrado. Por favor, instale o Git antes de continuar.
    pause
    exit /b
)

:: Initialize Git
if not exist .git (
    echo [*] Inicializando repositorio Git...
    git init
) else (
    echo [*] Repositorio Git ja inicializado.
)

:: Add files
echo [*] Adicionando arquivos (respeitando .gitignore)...
git add .

:: Commit
echo [*] Realizando commit inicial...
git commit -m "Initial commit: AutoTube Publisher base"

echo.
echo ========================================
echo   PROXIMOS PASSOS:
echo ========================================
echo 1. Crie um repositorio no GitHub (github.com/new).
echo 2. Copie a URL do seu repositorio (ex: https://github.com/seu-usuario/AutoTube_Publisher.git).
echo 3. Execute os seguintes comandos no terminal:
echo.
echo    git branch -M main
echo    git remote add origin SUA_URL_AQUI
echo    git push -u origin main
echo.
echo Pressione qualquer tecla para fechar...
pause >nul
