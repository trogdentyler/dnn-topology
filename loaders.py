import glob
import os
import random
from typing import TypeVar, Sequence, List

import matplotlib.pyplot as plt
import numpy as np
import torch
import torchvision
import torchvision.transforms as transforms
from PIL import Image  # , ImageFile
from PIL import PngImagePlugin
from torch.utils.data import (DataLoader, Dataset, RandomSampler,
                              SequentialSampler, Subset, random_split)


from config import IMG_SIZE, SUBSETS_LIST

T_co = TypeVar('T_co', covariant=True)

# uncomment these lines to allow large images and truncated images to be loaded
LARGE_ENOUGH_NUMBER = 1000
PngImagePlugin.MAX_TEXT_CHUNK = LARGE_ENOUGH_NUMBER * (1024**2)
# ImageFile.LOAD_TRUNCATED_IMAGES = True

# file where mappings from class codes to class names are stored
CODES_TO_NAMES_FILE = './results/codes_to_names.txt'

def get_color_distortion(s=0.125): # s is the strength of color distortion.
    color_jitter = transforms.ColorJitter(0.8*s, 0.8*s, 0.8*s, 0.2*s)
    rnd_color_jitter = transforms.RandomApply([color_jitter], p=0.8)
    rnd_gray = transforms.RandomGrayscale(p=0.2)
    color_distort = transforms.Compose([rnd_color_jitter, rnd_gray])

    return color_distort

def get_transform(train=True, crop=True, hflip=True, vflip=False, color_dis=True, blur=True, resize=False):
    transform = transforms.Compose([])

    if train:
        if crop:
            len_trans = len(transform.transforms)
            transform.transforms.insert(len_trans, transforms.RandomResizedCrop(size=(IMG_SIZE, IMG_SIZE), \
                                                                        interpolation=Image.BICUBIC))
        if hflip:
            len_trans = len(transform.transforms)
            transform.transforms.insert(len_trans, transforms.RandomHorizontalFlip())
        if color_dis:
            len_trans = len(transform.transforms)
            transform.transforms.insert(len_trans, get_color_distortion())
        if vflip:
            len_trans = len(transform.transforms)
            transform.transforms.insert(len_trans, transforms.RandomVerticalFlip())
        if resize:
            len_trans = len(transform.transforms)
            transform.transforms.insert(len_trans, transforms.Resize((32, 32), interpolation=Image.BICUBIC))
    else:
        if resize:
            len_trans = len(transform.transforms)
            transform.transforms.insert(len_trans, transforms.Resize((32, 32), interpolation=Image.BICUBIC))

    len_trans = len(transform.transforms)
    transform.transforms.insert(len_trans, transforms.ToTensor())

    return transform

def calc_mean_std(dataloader):
    pop_mean = []
    pop_std = []

    for _, data in enumerate(dataloader):
        image_batch = data[0]
        
        batch_mean = image_batch.mean(dim=[0,2,3])
        batch_std = image_batch.std(dim=[0,2,3])
        
        pop_mean.append(batch_mean.numpy())
        pop_std.append(batch_std.numpy())

    pop_mean = np.array(pop_mean).mean(axis=0)
    pop_std = np.array(pop_std).mean(axis=0)
    
    return pop_mean, pop_std

def get_dataset(data, path, transform, verbose, train=False, iter=0):
    ''' Return loader for torchvision data. If data in [mnist, cifar] torchvision.datasets has built-in loaders else load from ImageFolder '''
    if data == 'imagenet':
        dataset = CustomImageNet(path, 'data/map_clsloc.txt', subset=SUBSETS_LIST[iter], transform=transform, verbose=verbose, iter=iter)
    elif data == 'mnist':
        dataset = CustomMNIST(train=train, transform=transform)
    elif data.split('_')[0] == 'dummy':
        dataset = DummyDataset(transform=transform)
    else:
        dataset = torchvision.datasets.ImageFolder(path, transform=transform)

    return dataset

def seed_worker(worker_id):
    worker_seed = torch.initial_seed() % 2**32
    np.random.seed(worker_seed)
    random.seed(worker_seed)

def dataloader(data, path=None, train=False, transform=None, batch_size=1, iter=0, verbose=False, sampling=-1, \
               normalize=True, subset=None):
    dataset = get_dataset(data, path, transform, train=train, iter=iter, verbose=verbose)

    if data.split('_')[0] == 'dummy':
        dummy_transform = dataset.__gettransform__()

        proportions = [.7, .3]
        lengths = [int(p * len(dataset)) for p in proportions]
        lengths[-1] = len(dataset) - sum(lengths[:-1])

        train, test = random_split(dataset, lengths)

        if data.split('_')[1] == 'train':
            dataset = DummyDataset(train.dataset, transform=dummy_transform)
        else:
            dataset = DummyDataset(test.dataset, transform=dummy_transform)

    if sampling == -1:
        sampler = RandomSampler(dataset)
    else:
        sampler = SequentialSampler(dataset)

    if subset is not None:
        dataset = CustomSubset(dataset, subset)

    data_loader = DataLoader(dataset, batch_size=batch_size, sampler=sampler, num_workers=2, drop_last=True,  worker_init_fn=seed_worker)

    print("Transform before: ", dataset.__gettransform__(), "\n")

    if normalize and not isinstance(transform.transforms[-1], torchvision.transforms.transforms.Normalize):
        mean, std = calc_mean_std(data_loader)
        
        len_transform = len(dataset.__gettransform__().transforms)
        dataset.__gettransform__().transforms.insert(len_transform, transforms.Normalize(mean, std))

    print("Transform after: ", dataset.__gettransform__(), "\n")

    return data_loader

def loader(data, batch_size, verbose, iter=0, sampling=-1, subset=None):
    ''' Interface to the dataloader function '''

    # set data paths for different image sizes (32, 64, 256)
    if IMG_SIZE == 32:
        train_data_path = '/home/trogdent/imagenet_data/train_32'
        test_data_path = '/home/trogdent/imagenet_data/val_32'
    elif IMG_SIZE == 64:
        train_data_path = '/home/trogdent/imagenet_data/train_64'
        test_data_path = '/home/trogdent/imagenet_data/val_64'
    else:
        train_data_path = '/home/trogdent/imagenet_data/train'
        test_data_path = '/home/trogdent/imagenet_data/val'
    
    # return dataloader for different datasets and train/test splits
    if data == 'imagenet_train':
        transforms_tr_imagenet = get_transform(train=True, crop=True, hflip=True, vflip=False, blur=True)
        return dataloader('imagenet', train_data_path, transform=transforms_tr_imagenet, batch_size=batch_size, iter=iter, verbose=verbose, subset=subset) 
    elif data == 'imagenet_test':
        transforms_te_imagenet = get_transform(train=False, crop=False, hflip=False, vflip=False, blur=False)
        return dataloader('imagenet', test_data_path, transform=transforms_te_imagenet, batch_size=batch_size, iter=iter, verbose=verbose, subset=subset)
    elif data == 'mnist_train':
        transforms_tr_mnist = get_transform(train=True, crop=False, hflip=False, vflip=False, color_dis=False, blur=False, resize=True)
        return dataloader('mnist', train=True, transform=transforms_tr_mnist, batch_size=batch_size, iter=iter, verbose=verbose, normalize=True, subset=subset)
    elif data == 'mnist_test':
        transforms_te_mnist = get_transform(train=False, crop=False, hflip=False, vflip=False, color_dis=False, blur=False, resize=True)
        return dataloader('mnist', train=False, transform=transforms_te_mnist, batch_size=batch_size, iter=iter, verbose=verbose, normalize=True, subset=subset)
    elif data == 'dummy_train':
        dummy_transform = get_transform(train=False)
        return dataloader('dummy_train', transform=dummy_transform, batch_size=batch_size, subset=subset)
    elif data == 'dummy_test':
        dummy_transform = get_transform(train=False)
        return dataloader('dummy_test', transform=dummy_transform, batch_size=batch_size, subset=subset)
    else:
        raise ValueError(f"Invalid dataset: {data}")


class CustomImageNet(Dataset):

    def __init__(self, data_path, labels_path, verbose, subset=[], transform=None, grayscale=False, iter=0, num_samples=20000):
        super(CustomImageNet, self).__init__()
        
        self.data_path = data_path
        self.data = []
        self.label_dict = {}
        self.name_dict = {}
        self.transform = transform
        self.verbose = verbose
        
        if data_path == '/home/trogdent/imagenet_data/train' or data_path == '/home/trogdent/imagenet_data/val':
            img_format = '*.JPEG'
        else:
            img_format = '*.png'

        with open(labels_path, 'r') as f:
            for line in f:
                key = line.split()[0]
                value = int(line.split()[1])
                name = line.split()[2]
                
                if value in subset:
                    self.name_dict[key] = name
                    self.label_dict[key] = value

        for i, key in enumerate(self.label_dict.keys()):
            img_paths = glob.glob(os.path.join(data_path, key, img_format))

            lines = []
            if i in range(9) and self.verbose:
                lines.append("Label mapping: " + key + ' --> ' + str(i) + " " + self.name_dict[key] + "\n")
            elif self.verbose:
                lines.append("Label mapping: " + key + ' --> ' + str(i) + " " + self.name_dict[key] + "\n")
                lines.append("End of label mapping for subset " + str(subset) + " " + str(iter) + "\n")
                lines.append("\n")

            with open(CODES_TO_NAMES_FILE, 'a') as f:
                f.writelines(lines)

            counter = 0
            for img_path in img_paths:
                try:
                    img = Image.open(img_path)
                    img.load()
                except OSError:
                    print("Cannot open: {}".format(img_path))
                    continue

                if counter > num_samples:
                    break

                if img.mode == 'RGB' and not grayscale:
                    self.data.append((img, i))
                elif img.mode == 'L' and grayscale:
                    self.data.append((img, i))

                counter += 1

    def __len__(self):
        return len(self.data)
    
    def __getitem__(self, idx):
        img = self.data[idx][0]
        label = self.data[idx][1]

        img = self.transform(img)
        label = torch.tensor(label, dtype=torch.long)

        return (img, label)

    def __gettransform__(self):
        return self.transform    

class CustomMNIST(Dataset):
    def __init__(self, path='./data/mnist', train=True, transform=None):
        super(CustomMNIST).__init__()

        download = False if os.path.exists(path) else True
        os.makedirs(path, exist_ok=True)

        self.data = torchvision.datasets.MNIST(path, train=train, download=download, transform=transform)

    def __len__(self):
        return self.data.__len__()
    
    def __getitem__(self, idx):
        return self.data.__getitem__(idx)
    
    def __gettransform__(self):
        if hasattr(self.data, 'transform'):
            return getattr(self.data, 'transform')
        else:
            raise AttributeError("CustomMNIST has no attribute 'transform'")

class DummyDataset(Dataset):
    
    def __init__(self, data=None, transform=None, num_samples=10000):
        super(DummyDataset, self).__init__()

        self.data = data if data else []
        self.transform = transform
        self.num_samples = num_samples
    
        if data is None:
            self.generate_data(num_samples)
    
    def __len__(self):
        return self.num_samples
        
    def __getitem__(self, idx):
        img, label = self.data[idx]

        img = img
        label = label # this is a hack to make the label a tensor; the transform is simply ToTensor()
        
        return img, label

    def __gettransform__(self):
        return self.transform

    def generate_data(self, num_samples):
        for _ in range(num_samples):
            img = np.random.rand(3, 3).astype(np.float32)
            img, label = self.get_label(img)
                
            self.data.append((img, label))

    def get_label(self, img):
        rand_int = np.random.randint(low=0, high=3)
        
        img[rand_int, rand_int] = 0.
        
        label = rand_int
        # label = np.zeros(shape=3, dtype=int)
        # label[rand_int] = 1.

        return img, label
    
class CustomSubset(Dataset[T_co]):
    r"""
    Subset of a dataset at specified indices.

    Args:
        dataset (Dataset): The whole Dataset
        indices (sequence): Indices in the whole set selected for subset
    """
    dataset: Dataset[T_co]
    indices: Sequence[int]

    def __init__(self, dataset: Dataset[T_co], indices: Sequence[int]) -> None:
        self.dataset = dataset
        self.indices = indices

    def __getitem__(self, idx):
        if isinstance(idx, list):
            return self.dataset[[self.indices[i] for i in idx]]
        return self.dataset[self.indices[idx]]

    def __getitems__(self, indices: List[int]) -> List[T_co]:
        # add batched sampling support when parent dataset supports it.
        # see torch.utils.data._utils.fetch._MapDatasetFetcher
        if callable(getattr(self.dataset, "__getitems__", None)):
            return self.dataset.__getitems__([self.indices[idx] for idx in indices])  # type: ignore[attr-defined]
        else:
            return [self.dataset[self.indices[idx]] for idx in indices]

    def __len__(self):
        return len(self.indices)
    
    def __gettransform__(self):
        return self.dataset.__gettransform__()