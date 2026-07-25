#!/usr/bin/env bash
set -e
source /home/gonsgon/miniconda3/etc/profile.d/conda.sh
conda activate sam3d-blackwell
export CUDA_HOME="${CUDA_HOME:-/usr/local/cuda}"
export PATH="$CUDA_HOME/bin:${PATH:-}"
export CPATH="$CUDA_HOME/include:$CUDA_HOME/targets/x86_64-linux/include:${CPATH:-}"
export CPLUS_INCLUDE_PATH="$CUDA_HOME/include:$CUDA_HOME/targets/x86_64-linux/include:${CPLUS_INCLUDE_PATH:-}"
export LIBRARY_PATH="$CUDA_HOME/lib64:$CUDA_HOME/targets/x86_64-linux/lib:${LIBRARY_PATH:-}"
export LD_LIBRARY_PATH="$CUDA_HOME/lib64:$CUDA_HOME/targets/x86_64-linux/lib:${LD_LIBRARY_PATH:-}"
cd /home/gonsgon/sam3D/sam-3d-objects
python - <<'PY'
import sys
sys.path.insert(0, "notebook")
import inference
print("inference_import_ok")
PY
