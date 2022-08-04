"""
Creates color+normal datasets based on annotation file.
The datasets can be used to train MLP, CycleGAN, Pix2Pix models.
"""
import os
import cv2
import hydra
import imageio
import numpy as np
import torch

from src.third_party import data_utils
from src.dataio.generate_sphere_gt_normals import generate_sphere_gt_normals
from src.dataio.data_loader import data_loader
from src.dataio.create_csv import create_normal_csv, create_color_csv


@hydra.main(config_path="/home/shuk/digit-depth/config", config_name="rgb_to_normal.yaml",version_base=None)
def main(cfg):
    train_dataloader, train_dataset = data_loader(dir_dataset=os.path.join(cfg.base_path, "images"),
                                                  params=cfg.dataloader)
    dirs = [f"{cfg.base_path}/datasets/A/imgs", f"{cfg.base_path}/datasets/B/imgs",
            f"{cfg.base_path}/datasets/A/csv", f"{cfg.base_path}/datasets/B/csv"]
    for dir in dirs: os.makedirs(f"{dir}", exist_ok=True)
    # iterate over images
    img_idx = 0
    radius_bearing = np.int32(0.5 * 6.0 * cfg.mm_to_pixel)
    while img_idx < len(train_dataset):
        # read img + annotations
        data = train_dataset[img_idx]
        if cfg.dataloader.annot_flag:
            img, annot = data
            if annot.shape[0] == 0:
                img_idx = img_idx + 1
                continue
        else:
            img = data

        # get annotation circle params
        if cfg.dataloader.annot_flag:
            annot_np = annot.cpu().detach().numpy()
            center_y, center_x, radius_annot = annot_np[0][1], annot_np[0][0], annot_np[0][2]
        else:
            center_y, center_x, radius_annot = 0, 0, 0

        img_color_np = img.permute(2, 1, 0).cpu().detach().numpy()  # (3,320,240) -> (240,320,3)

        # apply foreground mask
        fg_mask = np.zeros(img_color_np.shape[:2], dtype='uint8')
        fg_mask = cv2.circle(fg_mask, (center_x, center_y), radius_annot, 255, -1)

        # 1. rgb -> normal (generate gt surface normals)
        img_mask = cv2.bitwise_and(img_color_np, img_color_np, mask=fg_mask)
        img_normal_np = generate_sphere_gt_normals(img_mask, center_x, center_y, radius=radius_bearing)

        # 2. downsample and convert to NumPy: (320,240,3) -> (160,120,3)
        img_normal_np = data_utils.interpolate_img(img=torch.tensor(img_normal_np).permute(2, 0, 1), rows=160, cols=120)
        img_normal_np = img_normal_np.permute(1, 2, 0).cpu().detach().numpy()
        img_color_ds = data_utils.interpolate_img(img=torch.tensor(img_color_np).permute(2, 0, 1), rows=160, cols=120)
        img_color_np = img_color_ds.permute(1, 2, 0).cpu().detach().numpy()

        # 3. save csv files for color and normal images

        if cfg.dataset.save_dataset:
            imageio.imwrite(f"{dirs[0]}/{img_idx:04d}.png", (img_color_np*255).astype(np.uint8))
            imageio.imwrite(f"{dirs[1]}/{img_idx:04d}.png", img_normal_np)
            print(f"Saved image {img_idx:04d}")
        img_idx += 1
    create_color_csv(save_dir=dirs[2], img_dir=dirs[0])
    create_normal_csv(save_dir=dirs[3], img_dir=dirs[1])


if __name__ == '__main__':
    main()