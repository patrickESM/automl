# Copyright 2020 Google Research. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
r"""Convert PASCAL dataset to TFRecord.


Example usage:
    python create_synth_DR_tfrecord.py  --data_dir=/tmp/VOCdevkit  \
        --year=VOC2012  --output_path=/tmp/pascal
"""

import hashlib
import io
import json
import os

from absl import app
from absl import flags
from absl import logging

from lxml import etree
import PIL.Image
import tensorflow as tf

from dataset import tfrecord_util

flags.DEFINE_string('data_dir', '', 'Root directory to raw synth DR data.')
flags.DEFINE_string('set', 'train', 'Convert training set, validation set or '
                                    'merged set.')
flags.DEFINE_string('annotations_dir', 'Annotations',
                    '(Relative) path to annotations directory.')
flags.DEFINE_string('year', 'ESM2020', 'Desired challenge year.')
flags.DEFINE_string('output_path', '', 'Path to output TFRecord and json.')
flags.DEFINE_string('label_map_json_path', None,
                    'Path to label map json file with a dictionary.')
flags.DEFINE_string('camera_settings_json_path', None,
                    'Path to camera settings json file with a dictionary.')
flags.DEFINE_boolean('ignore_difficult_instances', False, 'Whether to ignore '
                                                          'difficult instances')
flags.DEFINE_integer('num_shards', 1, 'Number of shards for output file.')
flags.DEFINE_integer('num_images', None, 'Max number of imags to process.')
FLAGS = flags.FLAGS

SETS = ['train', 'val', 'trainval', 'test']
YEARS = ['ESM2020', 'ESM2020_test', 'merged']

esm_label_map_dict = {
    'background': 0,
    'LGlove': 1,
    'RGlove': 2,
    'Shirt': 3,
    'Gown': 4,
    'Pants': 5,
    'Hat': 6,
    'Mask': 7,
    'Body': 8,
}

GLOBAL_IMG_ID = 0  # global image id.
GLOBAL_ANN_ID = 0  # global annotation id.


def get_image_id(filename):
    """Convert a string to a integer."""
    # Warning: this function is highly specific to pascal filename!!
    # Given filename like '2008_000002', we cannot use id 2008000002 because our
    # code internally will convert the int value to float32 and back to int, which
    # would cause value mismatch int(float32(2008000002)) != int(2008000002).
    # COCO needs int values, here we just use a incremental global_id, but
    # users should customize their own ways to generate filename.
    del filename
    global GLOBAL_IMG_ID
    GLOBAL_IMG_ID += 1
    return GLOBAL_IMG_ID


def get_ann_id():
    """Return unique annotation id across images."""
    global GLOBAL_ANN_ID
    GLOBAL_ANN_ID += 1
    return GLOBAL_ANN_ID


def dict_to_tf_example(data,
                       dataset_directory,
                       filepath,
                       camera_settings,
                       label_map_dict,
                       ignore_difficult_instances=False,
                       image_subdirectory='JPEGImages',
                       visibility_thresh=0.1,
                       ann_json_dict=None):
    """Convert XML derived dict to tf.Example proto.

    Notice that this function normalizes the bounding box coordinates provided
    by the raw data.

    Args:
      data: dict holding PASCAL XML fields for a single image (obtained by running
        tfrecord_util.recursive_parse_xml_to_dict)
      dataset_directory: Path to root directory holding PASCAL dataset
      label_map_dict: A map from string label names to integers ids.
      ignore_difficult_instances: Whether to skip difficult instances in the
        dataset  (default: False).
      image_subdirectory: String specifying subdirectory within the PASCAL dataset
        directory holding the actual image data.
      ann_json_dict: annotation json dictionary.

    Returns:
      example: The converted tf.Example.

    Raises:
      ValueError: if the image pointed to by data['filename'] is not a valid JPEG
    """

    img_path = filepath.split('.')[0] + '.jpg'
    with tf.io.gfile.GFile(img_path, 'rb') as fid:
        encoded_jpg = fid.read()
    encoded_jpg_io = io.BytesIO(encoded_jpg)
    image = PIL.Image.open(encoded_jpg_io)
    if image.format != 'JPEG':
        raise ValueError('Image format not JPEG')
    key = hashlib.sha256(encoded_jpg).hexdigest()


    width = int(camera_settings['captured_image_size']['width'])
    height = int(camera_settings['captured_image_size']['height'])
    image_id = img_path.split('.')[0].split('/')[-1]
    image_id = get_image_id(img_path)

    if ann_json_dict:
        image = {
            'file_name': img_path,
            'height': height,
            'width': width,
            'id': image_id,
        }
        ann_json_dict['images'].append(image)

    xmin = []
    ymin = []
    xmax = []
    ymax = []
    area = []
    classes = []
    classes_text = []
    truncated = []
    poses = []
    difficult_obj = []
    if 'objects' in data:
        for obj in data['objects']:

            difficult_obj.append(0)

            xmin.append(float(obj['bounding_box']['top_left'][1]) / width)
            ymin.append(float(obj['bounding_box']['top_left'][0]) / height)
            xmax.append(float(obj['bounding_box']['bottom_right'][1]) / width)
            ymax.append(float(obj['bounding_box']['bottom_right'][0]) / height)
            area.append((xmax[-1] - xmin[-1]) * (ymax[-1] - ymin[-1]))
            classes_text.append(obj['class'].encode('utf8'))
            classes.append(label_map_dict[obj['class']])
            visibility = obj['visibility']
            truncated.append(int(visibility > visibility_thresh))
            poses.append('Frontal'.encode('utf8'))

            if ann_json_dict:
                abs_xmin = int(obj['bounding_box']['top_left'][1])
                abs_ymin = int(obj['bounding_box']['top_left'][0])
                abs_xmax = int(obj['bounding_box']['bottom_right'][1])
                abs_ymax = int(obj['bounding_box']['bottom_right'][0])
                abs_width = abs_xmax - abs_xmin
                abs_height = abs_ymax - abs_ymin
                ann = {
                    'area': abs_width * abs_height,
                    'iscrowd': 0,
                    'image_id': image_id,
                    'bbox': [abs_xmin, abs_ymin, abs_width, abs_height],
                    'category_id': label_map_dict[obj['class']],
                    'id': get_ann_id(),
                    'ignore': 0,
                    'segmentation': [],
                }
                ann_json_dict['annotations'].append(ann)

    example = tf.train.Example(
        features=tf.train.Features(
            feature={
                'image/height':
                    tfrecord_util.int64_feature(height),
                'image/width':
                    tfrecord_util.int64_feature(width),
                'image/filename':
                    tfrecord_util.bytes_feature(img_path.encode('utf8')),
                'image/source_id':
                    tfrecord_util.bytes_feature(str(image_id).encode('utf8')),
                'image/key/sha256':
                    tfrecord_util.bytes_feature(key.encode('utf8')),
                'image/encoded':
                    tfrecord_util.bytes_feature(encoded_jpg),
                'image/format':
                    tfrecord_util.bytes_feature('jpeg'.encode('utf8')),
                'image/object/bbox/xmin':
                    tfrecord_util.float_list_feature(xmin),
                'image/object/bbox/xmax':
                    tfrecord_util.float_list_feature(xmax),
                'image/object/bbox/ymin':
                    tfrecord_util.float_list_feature(ymin),
                'image/object/bbox/ymax':
                    tfrecord_util.float_list_feature(ymax),
                'image/object/area':
                    tfrecord_util.float_list_feature(area),
                'image/object/class/text':
                    tfrecord_util.bytes_list_feature(classes_text),
                'image/object/class/label':
                    tfrecord_util.int64_list_feature(classes),
                'image/object/difficult':
                    tfrecord_util.int64_list_feature(difficult_obj),
                'image/object/truncated':
                    tfrecord_util.int64_list_feature(truncated),
                'image/object/view':
                    tfrecord_util.bytes_list_feature(poses),
            }))
    return example


def main(_):
    if FLAGS.set not in SETS:
        raise ValueError('set must be in : {}'.format(SETS))
    if FLAGS.year not in YEARS:
        raise ValueError('year must be in : {}'.format(YEARS))
    if not FLAGS.output_path:
        raise ValueError('output_path cannot be empty.')

    data_dir = FLAGS.data_dir
    years = ['ESM2020', 'ESM']
    if FLAGS.year != 'merged':
        years = [FLAGS.year]

    output_dir = os.path.dirname(FLAGS.output_path)
    if not tf.io.gfile.exists(output_dir):
        tf.io.gfile.makedirs(output_dir)
    logging.info('Writing to output directory: %s', output_dir)

    writers = [
        tf.io.TFRecordWriter(FLAGS.output_path + '-%05d-of-%05d.tfrecord' %
                             (i, FLAGS.num_shards))
        for i in range(FLAGS.num_shards)
    ]

    if FLAGS.label_map_json_path:
        with tf.io.gfile.GFile(FLAGS.label_map_json_path, 'rb') as f:
            labels = json.load(f)
            labels = labels['exported_object_classes']

            label_map_dict = {'background': 0}
            for idx, label in enumerate(labels):
                label_map_dict[label] = idx+1
    else:
        label_map_dict = esm_label_map_dict

    camera_settings = {}
    if FLAGS.camera_settings_json_path:
        with tf.io.gfile.GFile(FLAGS.camera_settings_json_path, 'rb') as f:
            labels = json.load(f)
            camera_settings = labels['camera_settings'][0]

    ann_json_dict = {
        'images': [],
        'type': 'instances',
        'annotations': [],
        'categories': []
    }
    for year in years:
        example_class = list(label_map_dict.keys())[1]

        curr_idx = 0
        for entry in sorted(os.scandir(os.path.join(data_dir, year)), key=lambda e: e.name):
            if entry.name.endswith('.json'):
                with tf.io.gfile.GFile(entry.path, 'rb') as f:
                    annotation = json.load(f)

                    for class_name, class_id in label_map_dict.items():
                        cls = {'supercategory': 'none', 'id': class_id, 'name': class_name}
                        ann_json_dict['categories'].append(cls)

                    if FLAGS.num_images and curr_idx >= FLAGS.num_images:
                        break
                    if curr_idx % 100 == 0:
                        logging.info('On image %d', curr_idx)

                    tf_example = dict_to_tf_example(
                        annotation,
                        FLAGS.data_dir,
                        entry.path,
                        camera_settings,
                        label_map_dict,
                        FLAGS.ignore_difficult_instances,
                        ann_json_dict=ann_json_dict)
                    writers[curr_idx % FLAGS.num_shards].write(tf_example.SerializeToString())

                    curr_idx += 1

    for writer in writers:
        writer.close()

    json_file_path = os.path.join(
        os.path.dirname(FLAGS.output_path),
        'json_' + os.path.basename(FLAGS.output_path) + '.json')
    with tf.io.gfile.GFile(json_file_path, 'w') as f:
        json.dump(ann_json_dict, f)


if __name__ == '__main__':
    app.run(main)
