@echo off
set PY=D:\envs\uw3dgs\python.exe
cd /d D:\uw3dgs
%PY% tools\build_s2_scene.py --level 0 --trial 1 && (echo SCENE_OK s2_turbid0) || (echo SCENE_FAIL s2_turbid0)
%PY% tools\build_s2_scene.py --level 3 --trial 1 && (echo SCENE_OK s2_turbid3) || (echo SCENE_FAIL s2_turbid3)
%PY% tools\build_s2_scene.py --level 5 --trial 1 && (echo SCENE_OK s2_turbid5) || (echo SCENE_FAIL s2_turbid5)
%PY% tools\build_s4_scene.py && (echo SCENE_OK s4_planenose) || (echo SCENE_FAIL s4_planenose)
echo BUILD_SUITE_DONE
