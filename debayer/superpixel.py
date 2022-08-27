import numpy as np
import tensorflow as tf

sp_kernel = tf.constant([
    [[[ 1.0, 0.0, 0.0 ]],
    [[ 0.0, 0.5, 0.0 ]]],
    [[[ 0.0, 0.5, 0.0 ]],
    [[ 0.0, 0.0, 0.1 ]]]
])

def debayer_superpixel(img):
    img = tf.constant(img, dtype=tf.float32)
    img = tf.expand_dims(img, axis=2)
    img = tf.expand_dims(img, axis=0)
    deb_img = tf.nn.conv2d(img, sp_kernel, strides=[2,2], padding='VALID')
    deb_img = tf.squeeze(deb_img)
    deb_img = tf.cast(deb_img / 256, tf.uint8)
    return deb_img.numpy()
