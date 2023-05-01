import torch
from torch import nn
from pathlib import Path
import numpy as np

def make_debayer():

    class DebayerModel(nn.Module):

      def __init__(self, device='cpu', size=(200,200)) -> None:
        super().__init__()

        r_m = np.zeros(size, dtype=np.float32)
        g_m = np.zeros(size, dtype=np.float32)
        b_m = np.zeros(size, dtype=np.float32)

        r_m[0::2, 0::2] = 1
        g_m[1::2, 0::2] = 1
        g_m[0::2, 1::2] = 1
        b_m[1::2, 1::2] = 1

        self.r_m = torch.tensor(r_m).to(device)
        self.g_m = torch.tensor(g_m).to(device)
        self.b_m = torch.tensor(b_m).to(device)

        # self.r_k = nn.Conv2d(in_channels=1, out_channels=1, kernel_size=3, stride=1, padding='same', padding_mode='replicate')
        # self.g_k = nn.Conv2d(in_channels=1, out_channels=1, kernel_size=3, stride=1, padding='same', padding_mode='replicate')
        # self.b_k = nn.Conv2d(in_channels=1, out_channels=1, kernel_size=3, stride=1, padding='same', padding_mode='replicate')
        self.k = nn.Conv2d(in_channels=3, out_channels=3, kernel_size=3, stride=1, padding='same', padding_mode='replicate')

      def forward(self, x):
        R = x * self.r_m
        G = x * self.g_m
        B = x * self.b_m

        x = torch.cat([R,G,B], dim=1)
        return self.k(x)

        # return torch.stack([self.r_k(x), self.g_k(x), self.b_k(x)])


    run_path = Path("../mlruns/0/cba518c62db649dfb2c4bd41ce4573ff/artifacts")

    dm = DebayerModel()
    dm.load_state_dict(torch.load(run_path / "weights_00019.pth"))
    dm.train(False)
    dm.to('cpu')

    def debayer(img):
      assert(len(img.shape)==2)
      assert(img.dtype == np.float32)
      h,w = img.shape
      def gap(x):
        if x % 200 == 0:
          gap = 0
        else:
          gap = 200 - (x%200)
        return gap
      img = np.pad(img, ((0, gap(h)), (0, gap(w))))
      bayered = np.expand_dims(np.expand_dims(img, axis=0), axis=0)
      rgb_out = np.zeros((img.shape[0], img.shape[1], 3), dtype=np.uint8)
      for y in range(0, img.shape[0], 200):
          for x in range(0, img.shape[1], 200):

            rgb_f = dm(torch.tensor(bayered[:, :, y:y+200, x:x+200]))
            rgb_i = (rgb_f * 255.0).detach().numpy().astype(np.uint8)
            rgb_img = np.transpose(rgb_i[0], axes=(1, 2, 0))

            rgb_out[y:y+200, x:x+200, :] = rgb_img

      return rgb_out[0:h,0:w,:]
    return debayer


if __name__ == "__main__":
    img = np.zeros((431, 432), dtype=np.float32)
    debayer = make_debayer()
    deb = debayer(img)
    print(deb.shape)
