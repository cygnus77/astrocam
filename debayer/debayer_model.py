import torch
from torch import nn
import torch.nn.functional as F
from torch.utils.data import Dataset
from torch.utils.data import DataLoader
import argparse
import numpy as np
import torch.optim as optim
import cairo
from random import random, choice
from pathlib import Path
from itertools import product

class DebayerModel(nn.Module):

  def __init__(self, device='cpu') -> None:
    super().__init__()

    r_m = np.zeros((200,200), dtype=np.float32)
    g_m = np.zeros((200,200), dtype=np.float32)
    b_m = np.zeros((200,200), dtype=np.float32)

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

    # return torch.stach([self.r_k(R), self.g_k(G), self.b_k(B)])


def train(net, trainloader, testloader, weights_dir: Path):
  if not weights_dir.exists():
    weights_dir.mkdir(exist_ok=True, parents=True)

  criterion = nn.L1Loss(reduction='sum')
  optimizer = optim.Adam(net.parameters())

  for epoch in range(50):  # loop over the dataset multiple times

    running_loss = 0.0
    mini_batch = 20
    for i, data in enumerate(trainloader, 0):
        # get the inputs; data is a list of [inputs, labels]
        inputs, labels = data

        # zero the parameter gradients
        optimizer.zero_grad()

        # forward + backward + optimize
        outputs = net(inputs)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        # print statistics
        running_loss += loss.item()
        if i % mini_batch == mini_batch-1:    # print every 2000 mini-batches
            print(f'[{epoch + 1}, {i + 1:5d}] loss: {running_loss / mini_batch:.3f}')
            running_loss = 0.0

    torch.save(net.state_dict(), weights_dir / f"weights_{epoch:05d}.pth")

    total_loss = 0
    with torch.no_grad():
      for data in testloader:
          images, labels = data
          outputs = net(images)
          loss = criterion(outputs, labels)
          total_loss += loss

      print(f'Ave test loss: {total_loss / len(testloader)} %')

  print('Finished Training')


class RRGBDataGenetator(Dataset):

  def __init__(self, datafolder: Path) -> None:
    super().__init__()
    self.datafiles = list(datafolder.glob("*.npz"))

  def __len__(self):
    return len(self.datafiles)

  def __getitem__(self, idx):
    sample = np.load(self.datafiles[idx], allow_pickle=True)

    bayered = torch.tensor(sample["bayered"], device='cuda')
    rgb = torch.tensor(sample["rgb"], device='cuda')

    return (bayered, rgb)

  @staticmethod
  def make_dataset(datafolder: Path, numsamples=500):
    datafolder.mkdir(exist_ok=True, parents=True)
    colors = list(product((0,1), (0,1), (0,1)))[1:]

    def _make_star(w=200, h=200):
      img = np.zeros(shape=(h, w), dtype=np.uint32)
      with cairo.ImageSurface.create_for_data(img, cairo.FORMAT_ARGB32, w, h) as surface:
          context = cairo.Context(surface)
          context.set_antialias(cairo.Antialias.BEST)
          context.set_source_rgb(0,0,0)
          context.fill()
          x1, y1 = random(), random()
          x2, y2 = random(), random()
          r = random()
          print(f"c1:{x1},{y1}, c2:{x2},{y2}, r:{r}")
          pat = cairo.RadialGradient(x1, y1, 0, x2, y2, r)
          pat.set_matrix(cairo.Matrix(xx=1/w, yy=1/h))
          pat.add_color_stop_rgb(0, *choice(colors))
          pat.add_color_stop_rgb(1, 0, 0, 0)
          context.set_source(pat)
          context.scale(w, h)
          context.rectangle(0, 0, 1, 1)
          context.fill()
      r=(img >>16) & 0xff
      g=(img >>8) & 0xff
      b=img & 0xff
      return np.stack([r.astype(np.uint8),g.astype(np.uint8),b.astype(np.uint8)], axis=2)

    def rggb(img):
      r_m = np.zeros(shape=img.shape[:2], dtype=np.uint8)
      r_m[0::2, 0::2] = 1
      g1_m = np.zeros(shape=img.shape[:2], dtype=np.uint8)
      g1_m[0::2, 1::2] = 1
      g2_m = np.zeros(shape=img.shape[:2], dtype=np.uint8)
      g2_m[1::2, 0::2] = 1
      b_m = np.zeros(shape=img.shape[:2], dtype=np.uint8)
      b_m[1::2, 1::2] = 1
      return (img[:,:,0] * r_m) + (img[:,:,1] * g1_m) + (img[:,:,1] * g2_m) + (img[:,:,2] * b_m)

    for idx in range(numsamples):
      rgb = _make_star()
      bayered = rggb(rgb)

      rgb = rgb.astype(np.float32)
      rgb = np.transpose(rgb, axes=(2,0,1))
      rgb = rgb / 255.0

      bayered = bayered.astype(np.float32)
      bayered = np.expand_dims(bayered, axis=0)
      bayered = bayered / 255.0

      np.savez(datafolder/f"{idx:05d}.npz", allow_pickle=True, bayered=bayered, rgb=rgb)


if __name__ == "__main__":

  train_dataset_dir = Path("dataset/train")
  if not train_dataset_dir.exists():
    RRGBDataGenetator.make_dataset(train_dataset_dir, 5000)

  test_dataset_dir = Path("dataset/test")
  if not test_dataset_dir.exists():
    RRGBDataGenetator.make_dataset(test_dataset_dir, 500)
  
  train_dataset = RRGBDataGenetator(train_dataset_dir)
  test_dataset = RRGBDataGenetator(test_dataset_dir)
  
  trainloader = DataLoader(train_dataset, batch_size=8, shuffle=True)
  testloader = DataLoader(test_dataset, batch_size=8, shuffle=False)

  dm = DebayerModel('cuda')
  dm.train(True)
  dm.to('cuda')
  train(dm, trainloader, testloader, weights_dir = Path("weights"))


  # img = torch.rand((200*2, 200*2))
  # img = img.unsqueeze(0)
  # print(img.shape)
  # output = dm(img)
  # print(output.shape)

  # ap = argparse.ArgumentParser()
  # ap.add_argument("mode")
  # args = ap.parse_args()

  # if args.mode == 'train':

