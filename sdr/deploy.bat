@echo off
set TARGET_IP=192.168.1.50
set REMOTE_USER=root
set REMOTE_DIR=/root/led

echo [1/3] Verifying and creating remote directory '%REMOTE_DIR%'...
:: The -p flag prevents errors if the folder already exists
ssh %REMOTE_USER%@%TARGET_IP% "mkdir -p %REMOTE_DIR%"

echo [2/3] Copying and updating .py files...
:: This copies all Python files from the directory where the .bat is run
scp *.py %REMOTE_USER%@%TARGET_IP%:%REMOTE_DIR%/

echo Transfer complete!

echo [3/3] Executing the Python script...
@REM ssh %BOARD_USER%@%BOARD_IP% "python3 %REMOTE_DIR%/your_script.py"
ssh %REMOTE_USER%@%TARGET_IP% "python3 %REMOTE_DIR%/main.py"

pause


@REM delete all: root@analog:~/led# rm *   
@REM setup ip for my laptop: 192.168.1.10 
@REM setup ip for the board: ifconfig eth0 192.168.1.50 netmask 255.255.255.0 up  
@REM check ip of the board: ifconfig eth0
@REM connecting to the board (from the VS Terminal): ssh root@192.168.1.50   
@REM the psw to the board: analog
@REM run all: python3 /root/led/main.py   