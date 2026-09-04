@echo off
setlocal
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b %errorlevel%
set GIT_CONFIG_COUNT=1
set GIT_CONFIG_KEY_0=safe.directory
set GIT_CONFIG_VALUE_0=C:/Solo WotLK/WoWBotServer/azerothcore-wotlk
pushd "C:\Solo WotLK\WoWBotServer\build-solitary-v4-ninja"
"C:\Program Files\Microsoft Visual Studio\18\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja\ninja.exe" -j8 worldserver
set BUILD_RESULT=%errorlevel%
popd
exit /b %BUILD_RESULT%
