import numpy as np
import tensorflow as tf

sp_kernel = tf.constant([
    [[[ 1.0, 0.0, 0.0 ]],
    [[ 0.0, 0.5, 0.0 ]]],
    [[[ 0.0, 0.5, 0.0 ]],
    [[ 0.0, 0.0, 0.1 ]]]
])

def debayer_superpixel(img):
    assert(len(img.shape)==3, f"Image must 3 dims (WxHx1), but has {len(img.shape)} dims")
    assert(img.shape[2]==1, f"Last dim must be 1 (WxHx1), but has {len(img.shape)} dims with 1st dim={img.shape[2]}")
    src_dtype = img.dtype
    img = tf.constant(img, dtype=tf.float32)
    img = tf.expand_dims(img, axis=0)
    deb_img = tf.nn.conv2d(img, sp_kernel, strides=[2,2], padding='VALID')
    deb_img = tf.squeeze(deb_img)
    deb_img = tf.cast(deb_img, src_dtype)
    return deb_img.numpy()
