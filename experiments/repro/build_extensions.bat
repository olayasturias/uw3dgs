@echo off
REM Build all CUDA extensions for the shared uw3dgs env against torch 2.4.1+cu124.
call "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat"
set DISTUTILS_USE_SDK=1
set TORCH_CUDA_ARCH_LIST=8.6
set PY=D:\envs\uw3dgs\python.exe
set R=D:\uw3dgs\repos

echo ============ diff_gaussian_rasterization (dr_aa, gaussian-splatting) ============
%PY% -m pip install --no-build-isolation "%R%\gaussian-splatting\submodules\diff-gaussian-rasterization" || echo BUILD_FAILED diff_gaussian_rasterization
echo ============ simple_knn ============
%PY% -m pip install --no-build-isolation "%R%\gaussian-splatting\submodules\simple-knn" || echo BUILD_FAILED simple_knn
echo ============ fused_ssim ============
%PY% -m pip install --no-build-isolation "%R%\gaussian-splatting\submodules\fused-ssim" || echo BUILD_FAILED fused_ssim
echo ============ dgr_seasplat ============
%PY% -m pip install --no-build-isolation "%R%\seasplat\submodules\diff-gaussian-rasterization" || echo BUILD_FAILED dgr_seasplat
echo ============ dgr_main (recgs) ============
%PY% -m pip install --no-build-isolation "%R%\recgs\submodules\diff-gaussian-rasterization" || echo BUILD_FAILED dgr_main
echo ============ dgr_uwgs ============
%PY% -m pip install --no-build-isolation "%R%\UW-GS\submodules\diff-gaussian-rasterization" || echo BUILD_FAILED dgr_uwgs
echo ============ dgr_rus ============
%PY% -m pip install --no-build-isolation "%R%\RUSplatting\submodules\diff-gaussian-rasterization" || echo BUILD_FAILED dgr_rus
echo ============ dgr_uir ============
%PY% -m pip install --no-build-isolation "%R%\3D-UIR\submodules\diff-gaussian-rasterization" || echo BUILD_FAILED dgr_uir

echo ============ import check ============
%PY% -c "import importlib; mods=['diff_gaussian_rasterization','simple_knn','fused_ssim','dgr_seasplat','dgr_main','dgr_uwgs','dgr_rus','dgr_uir']; [print(m, ':', 'OK' if importlib.import_module(m) else '?') for m in mods]"
