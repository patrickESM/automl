# Brain AutoML

This repository contains a list of AutoML related models and libraries.

Same as official automl repo but with new webcam runmode in model_inspect.py
to run the model with webcam do the following after checking the repo out:

## call this in terminal for webcam demo:
```
cd efficientdet
wget https://storage.googleapis.com/cloud-tpu-checkpoints/efficientdet/coco/efficientdet-d0.tar.gz
wget https://storage.googleapis.com/cloud-tpu-checkpoints/efficientdet/coco/efficientdet-d4.tar.gz
tar zxf efficientdet-d0.tar.gz
tar zxf efficientdet-d4.tar.gz
python model_inspect.py --runmode=saved_model --model_name=efficientdet-d4 --ckpt_path=efficientdet-d4 --hparams="mixed_precision=true" --saved_model_dir='savedmodel'
python model_inspect.py --runmode=webcam --model_name=efficientdet-d4 --saved_model_dir='savedmodel' --min_score_thresh=0.35 --max_boxes_to_draw=200 --hparams="mixed_precision=true"
```
