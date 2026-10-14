@echo off
rem  Wie build_exe.bat, aber OHNE Selbsttest (schneller).
call "%~dp0build_exe.bat" --skip-test
