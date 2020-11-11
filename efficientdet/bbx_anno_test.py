import cv2
import json

with open('efficientdet/smpl_test/ESM2020_test/000000.json') as f:
    data = json.load(f)

    for object in data['objects']:

        print(object['class'])
        top_left_tmp = [0.0, 0.0]
        top_left = object['bounding_box']['top_left']
        top_left_tmp[0] = int(top_left[1])
        top_left_tmp[1] = int(top_left[0])

        bottom_right_tmp = [0.0, 0.0]
        bottom_right = object['bounding_box']['bottom_right']
        bottom_right_tmp[0] = int(bottom_right[1])
        bottom_right_tmp[1] = int(bottom_right[0])

        img = cv2.imread('efficientdet/smpl_test/ESM2020_test/000000.jpg')

        cv2.rectangle(img, tuple(top_left_tmp), tuple(bottom_right_tmp), (0, 255, 0), 2)

        cv2.imshow('test', img)
        if cv2.waitKey(0) & 0xFF == ord('q'):
            break

cv2.destroyAllWindows()
