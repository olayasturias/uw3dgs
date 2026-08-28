#!/bin/sh
# Decide the SOTRUE pose convention empirically: triangulate with fixed poses
# under each candidate rotation convention; the right one produces a dense,
# low-error model. Features/matches are pose-independent -> computed once.
set -e
COLMAP=${COLMAP:-colmap}
PY=${PY:-python}
IMG=${IMG:?set IMG to <SOTRUE>/trial1/turbid0/left}
CSV=${CSV:?set CSV to the interpolated left-camera timestamps for turbid0/trial1}
W=${W:-./convtest}
CAM="OPENCV,1920,1216,788.57634,787.13041,980.65685,571.03147,-0.016788,-0.002846,-0.003082,-0.000599"

mkdir -p $W
# image list = every 8th pose row's image
$PY "$(dirname "$0")/pose2colmap.py" --source sotrue --poses $CSV --out $W/model_c2w_optical --rot-mode c2w_optical --subsample 8 --camera "$CAM"
$PY "$(dirname "$0")/pose2colmap.py" --source sotrue --poses $CSV --out $W/model_w2c_optical --rot-mode w2c_optical --subsample 8 --camera "$CAM"
$PY "$(dirname "$0")/pose2colmap.py" --source sotrue --poses $CSV --out $W/model_c2w_ros     --rot-mode c2w_ros     --subsample 8 --camera "$CAM"
awk '{print $10}' $W/model_c2w_optical/images.txt | grep -v '^$' > $W/list.txt
wc -l $W/list.txt

if [ ! -f $W/db.db ]; then
  $COLMAP feature_extractor --database_path $W/db.db --image_path $IMG \
      --image_list_path $W/list.txt --ImageReader.single_camera 1 \
      --ImageReader.camera_model OPENCV \
      --ImageReader.camera_params "788.57634,787.13041,980.65685,571.03147,-0.016788,-0.002846,-0.003082,-0.000599" \
      > $W/feat.log 2>&1
  $COLMAP exhaustive_matcher --database_path $W/db.db > $W/match.log 2>&1
fi

for MODE in c2w_optical w2c_optical c2w_ros; do
  echo "=============== $MODE ==============="
  rm -rf $W/tri_$MODE; mkdir -p $W/tri_$MODE
  $COLMAP point_triangulator --database_path $W/db.db --image_path $IMG \
      --input_path $W/model_$MODE --output_path $W/tri_$MODE > $W/tri_$MODE.log 2>&1 || echo "TRIANGULATION FAILED $MODE"
  $COLMAP model_analyzer --path $W/tri_$MODE 2>&1 | grep -E "Points|Observations|Mean track|Mean observations|Mean reprojection" || echo "no model"
done
