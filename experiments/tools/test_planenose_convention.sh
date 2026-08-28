#!/bin/sh
# Same empirical convention test for EIVA plane_nose pose_gt.txt.
set -e
COLMAP=/d/uw3dgs/colmap/bin/colmap.exe
PY=/d/envs/uw3dgs/python.exe
IMG=/d/Datasets/EIVA/vobster_quay/plane_nose/processed/left
POSES=/d/Datasets/EIVA/vobster_quay/plane_nose/pose_gt.txt
W=/d/uw3dgs/convtest_pn
CAM="PINHOLE,2816,2816,1847.5905420747683,1847.5905420747683,1391.3,1407.177"

mkdir -p $W
for MODE in w2c_direct w2c_direct_gl c2w_optical_gl; do
  $PY /d/uw3dgs/tools/pose2colmap.py --source planenose --poses $POSES --out $W/model_$MODE --rot-mode $MODE --subsample 8 --camera "$CAM"
done
awk '{print $10}' $W/model_c2w_optical/images.txt | grep -v '^$' > $W/list.txt
wc -l $W/list.txt

if [ ! -f $W/db.db ]; then
  $COLMAP feature_extractor --database_path $W/db.db --image_path $IMG \
      --image_list_path $W/list.txt --ImageReader.single_camera 1 \
      --ImageReader.camera_model PINHOLE \
      --ImageReader.camera_params "1847.5905420747683,1847.5905420747683,1391.3,1407.177" \
      > $W/feat.log 2>&1
  $COLMAP exhaustive_matcher --database_path $W/db.db > $W/match.log 2>&1
fi

for MODE in w2c_direct w2c_direct_gl c2w_optical_gl; do
  echo "=============== $MODE ==============="
  rm -rf $W/tri_$MODE; mkdir -p $W/tri_$MODE
  $COLMAP point_triangulator --database_path $W/db.db --image_path $IMG \
      --input_path $W/model_$MODE --output_path $W/tri_$MODE > $W/tri_$MODE.log 2>&1 || echo "TRIANGULATION FAILED $MODE"
  $COLMAP model_analyzer --path $W/tri_$MODE 2>&1 | grep -E "Points|Observations|Mean track|Mean observations|Mean reprojection" || echo "no model"
done
