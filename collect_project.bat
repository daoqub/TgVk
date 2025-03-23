@echo off
chcp 65001 > nul
echo Сборка всех Python файлов в один текстовый файл...

:: Указываем имя выходного файла
set OUTPUT_FILE=project_combined.txt

:: Удаляем старый файл, если он существует
if exist %OUTPUT_FILE% del %OUTPUT_FILE%

:: Создаем заголовок для структуры каталога
echo ============================================================================= >> %OUTPUT_FILE%
echo СТРУКТУРА КАТАЛОГА: >> %OUTPUT_FILE%
echo ============================================================================= >> %OUTPUT_FILE%
echo. >> %OUTPUT_FILE%

:: Собираем структуру каталога с файлами .py
for /r %%f in (*.py) do (
    setlocal enabledelayedexpansion
    set REL_PATH=%%f
    set REL_PATH=!REL_PATH:%cd%\=!
    echo !REL_PATH! >> %OUTPUT_FILE%
    endlocal
)

echo. >> %OUTPUT_FILE%
echo ============================================================================= >> %OUTPUT_FILE%
echo СОДЕРЖИМОЕ ФАЙЛОВ: >> %OUTPUT_FILE%
echo ============================================================================= >> %OUTPUT_FILE%
echo. >> %OUTPUT_FILE%

:: Собираем содержимое всех файлов .py в выходной файл
for /r %%f in (*.py) do (
    setlocal enabledelayedexpansion
    set REL_PATH=%%f
    set REL_PATH=!REL_PATH:%cd%\=!
    echo. >> %OUTPUT_FILE%
    echo ============================================================================= >> %OUTPUT_FILE%
    echo ФАЙЛ: !REL_PATH! >> %OUTPUT_FILE%
    echo ============================================================================= >> %OUTPUT_FILE%
    echo. >> %OUTPUT_FILE%
    type "%%f" >> %OUTPUT_FILE%
    echo. >> %OUTPUT_FILE%
    endlocal
)

echo Сборка завершена. Все файлы сохранены в %OUTPUT_FILE%.
pause
