@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat"
set DISTUTILS_USE_SDK=1
set TORCH_CUDA_ARCH_LIST=8.6
set TCNN_CUDA_ARCHITECTURES=86
set PY=D:\envs\uw3dgs\python.exe
set R=D:\uw3dgs\repos

echo ============ tiny-cuda-nn ============
%PY% -m pip install --no-build-isolation "git+https://github.com/NVlabs/tiny-cuda-nn/#subdirectory=bindings/torch" || echo BUILD_FAILED tinycudann

echo ============ water-splatting (editable, builds water_splatting.csrc) ============
%PY% -m pip install --no-build-isolation -e "%R%\water-splatting" || echo BUILD_FAILED water_splatting

echo ============ SeaFree-GS vendored gsplat 1.4.0 (replaces PyPI gsplat) ============
%PY% -m pip uninstall -y gsplat
%PY% -m pip install --no-build-isolation "%R%\SeaFree-GS\third_party\gsplat" || echo BUILD_FAILED gsplat_vendored

echo ============ SeaFree-GS (editable) ============
%PY% -m pip install --no-build-isolation -e "%R%\SeaFree-GS" || echo BUILD_FAILED seafree_gs

echo ============ import check ============
%PY% -c "import tinycudann; print('tinycudann OK', tinycudann.__version__)"
%PY% -c "import water_splatting; print('water_splatting OK')"
%PY% -c "import gsplat; print('gsplat OK', gsplat.__version__)"
%PY% -c "import seafree_gs; print('seafree_gs OK')" 2>&1
echo ============ ns method registry ============
%PY% -c "from nerfstudio.configs.method_configs import all_methods; import sys; ms=sorted(all_methods); print([m for m in ms if 'water' in m or 'seafree' in m or 'splat' in m])"
