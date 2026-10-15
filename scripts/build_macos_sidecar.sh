#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
cd "$project_dir"
"$project_dir/.venv-mlx/bin/python" -m PyInstaller --noconfirm --clean --onedir \
  --name legalredaction-service \
  --collect-all mlx \
  --collect-all mlx_lm \
  --hidden-import service.local_api \
  --distpath dist-sidecar \
  --workpath build/pyinstaller \
  --specpath build \
  service/sidecar_main.py

echo "Sidecar ready: $project_dir/dist-sidecar/legalredaction-service/legalredaction-service"
