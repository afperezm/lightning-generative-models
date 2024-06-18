from pathlib import Path
from typing import Optional, Union

import pytorch_lightning as pl
import torch
from torch.utils.data import DataLoader, random_split
from torchvision import datasets, transforms
from tqdm import tqdm

from data.dataLoader import SEN12MSCR
from utils.path import DATASET_PATH


class CenterCropMinXY(object):
    """
    Custom transform that performs a center crop on the image in the smaller dimension (X or Y).
    """
    def __call__(self, image):
        assert type(image) == torch.Tensor
        # Get the height and width of the image
        _, h, w = image.shape
        # Determine the smaller dimension
        min_dim = min(h, w)
        # Calculate top and left coordinates for cropping
        top = (h - min_dim) // 2
        left = (w - min_dim) // 2
        # Perform the crop
        image = image[:, top: top + min_dim, left: left + min_dim]
        # Update the sample dictionary
        return image


class DataModule(pl.LightningDataModule):
    def __init__(
        self,
        name: str,
        img_size: int,
        img_channels: int,
        data_dir: Union[str, Path] = DATASET_PATH,
        batch_size: int = 32,
        num_workers: int = 0,
        pin_memory: bool = True,
        persistent_workers: bool = True,
        train_val_split: float = 0.8,
        download: bool = True,
    ):
        super().__init__()
        self.name = str(name)
        self.data_dir = data_dir
        self.img_size = img_size
        self.img_channels = img_channels
        self.batch_size = int(batch_size / (torch.cuda.device_count() if torch.cuda.device_count() > 1 else 1))
        self.num_workers = num_workers
        self.pin_memory = pin_memory
        self.persistent_workers = persistent_workers
        self.train_val_split = train_val_split
        self.download = download

        self.sanity_check()
        self.transforms = {
            "train": transforms.Compose(
                [
                    transforms.ToTensor(),
                    transforms.Normalize(
                        [0.5] * self.img_channels,
                        [0.5] * self.img_channels,
                    ),
                    CenterCropMinXY(),
                    transforms.Resize(self.img_size, antialias=True),
                    transforms.RandomHorizontalFlip(0.5),
                ]
            ),
            "val": transforms.Compose(
                [
                    transforms.ToTensor(),
                    transforms.Normalize(
                        [0.5] * self.img_channels,
                        [0.5] * self.img_channels,
                    ),
                    CenterCropMinXY(),
                    transforms.Resize(self.img_size, antialias=True),
                ]
            ),
            "test": transforms.Compose(
                [
                    transforms.ToTensor(),
                    transforms.Normalize(
                        [0.5] * self.img_channels,
                        [0.5] * self.img_channels,
                    ),
                    CenterCropMinXY(),
                    transforms.Resize(self.img_size, antialias=True),
                ]
            ),
        }

    def prepare_data(self) -> None:
        """Download the data."""
        if self.name == "MNIST":
            datasets.MNIST(self.data_dir, train=True, download=self.download)
            datasets.MNIST(self.data_dir, train=False, download=self.download)

        elif self.name == "CelebA":
            for split in tqdm(
                ["train", "valid", "test"], desc="Downloading CelebA Dataset"
            ):
                datasets.CelebA(
                    self.data_dir,
                    split=split,
                    download=self.download,
                    target_type="attr",
                )

        elif self.name == "Flowers102":
            for split in tqdm(
                ["train", "val", "test"], desc="Downloading Flowers102 Dataset"
            ):
                datasets.Flowers102(self.data_dir, split=split, download=self.download)

    def setup(self, stage: Optional[str] = None) -> None:
        """Setup datasets for training, validation, and testing."""
        if self.name == "MNIST":
            full_train_dataset = datasets.MNIST(
                self.data_dir,
                train=True,
                transform=self.transforms["train"],
            )
            num_train = int(len(full_train_dataset) * self.train_val_split)
            num_val = len(full_train_dataset) - num_train
            self.train_dataset, self.val_dataset = random_split(
                full_train_dataset, [num_train, num_val]
            )
            self.test_dataset = datasets.MNIST(
                self.data_dir,
                train=False,
                transform=self.transforms["test"],
            )

        elif self.name == "LSUN":
            classes = ["bedroom"]

            train_classes = [f"{sub_class}_train" for sub_class in classes]
            val_classes = [f"{sub_class}_val" for sub_class in classes]
            test_classes = [f"{sub_class}_val" for sub_class in classes]

            self.train_dataset = datasets.LSUN(
                root=self.data_dir / "LSUN",
                classes=train_classes,
                transform=self.transforms["train"],
            )
            self.val_dataset = datasets.LSUN(
                root=self.data_dir / "LSUN",
                classes=val_classes,
                transform=self.transforms["val"],
            )
            self.test_dataset = datasets.LSUN(
                root=self.data_dir / "LSUN",
                classes=test_classes,
                transform=self.transforms["test"],
            )

        elif self.name == "CelebA":
            self.train_dataset = datasets.CelebA(
                self.data_dir,
                split="train",
                target_type="attr",
                transform=self.transforms["train"],
            )
            self.val_dataset = datasets.CelebA(
                self.data_dir,
                split="valid",
                target_type="attr",
                transform=self.transforms["val"],
            )
            self.test_dataset = datasets.CelebA(
                self.data_dir,
                split="test",
                target_type="attr",
                transform=self.transforms["test"],
            )

        elif self.name == "Flowers102":
            self.train_dataset = datasets.Flowers102(
                self.data_dir,
                split="train",
                transform=self.transforms["train"],
            )
            self.val_dataset = datasets.Flowers102(
                self.data_dir,
                split="val",
                transform=self.transforms["val"],
            )
            self.test_dataset = datasets.Flowers102(
                self.data_dir,
                split="test",
                transform=self.transforms["test"],
            )

        elif self.name == "SEN12MSCR":

            self.train_dataset = SEN12MSCR(
                root=self.data_dir,
                split="train",
                transform=self.transforms["train"]
            )

            self.val_dataset = SEN12MSCR(
                root=self.data_dir,
                split="val",
                transform=self.transforms["val"]
            )

            self.test_dataset = SEN12MSCR(
                root=self.data_dir,
                split="test",
                transform=self.transforms["test"]
            )

    def train_dataloader(self) -> DataLoader:
        return DataLoader(
            self.train_dataset,
            batch_size=self.batch_size,
            num_workers=self.num_workers,
            pin_memory=self.pin_memory,
            persistent_workers=self.persistent_workers,
            shuffle=True,
        )

    def val_dataloader(self) -> DataLoader:
        return DataLoader(
            self.val_dataset,
            batch_size=self.batch_size,
            num_workers=self.num_workers,
            pin_memory=self.pin_memory,
            persistent_workers=self.persistent_workers,
        )

    def test_dataloader(self) -> DataLoader:
        return DataLoader(
            self.test_dataset,
            batch_size=self.batch_size,
            num_workers=self.num_workers,
            pin_memory=self.pin_memory,
            persistent_workers=self.persistent_workers,
        )

    def sanity_check(self):
        if self.name == "MNIST":
            assert self.img_channels == 1, "MNIST dataset supports `img_channels=1`."
        elif self.name == "SEN12MSCR":
            assert self.img_channels == 2, "SEN12MSCR dataset supports `img_channels=3`."
        else:
            assert (
                self.img_channels == 3
            ), f"{self.name} dataset supports `img_channels=3`."
