import glob
import os
import random

import numpy as np
import torch
import torchvision
import torchvision.transforms as transforms
from PIL import Image 
from PIL import PngImagePlugin
from torch.utils.data import (DataLoader, Dataset, RandomSampler,
                              SequentialSampler, Subset, random_split)

from config import IMG_SIZE, SUBSETS_LIST, SEED

# uncomment these lines to allow large images and truncated images to be loaded
LARGE_ENOUGH_NUMBER = 1000
PngImagePlugin.MAX_TEXT_CHUNK = LARGE_ENOUGH_NUMBER * (1024**2)

# file where mappings from class codes to class names are stored
CODES_TO_NAMES_FILE = './results/codes_to_names.txt'

def get_color_distortion(s=0.125): # s is the strength of color distortion.
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    random.seed(SEED)

    color_jitter = transforms.ColorJitter(0.8*s, 0.8*s, 0.8*s, 0.2*s)
    rnd_color_jitter = transforms.RandomApply([color_jitter], p=0.8)
    rnd_gray = transforms.RandomGrayscale(p=0.2)
    color_distort = transforms.Compose([rnd_color_jitter, rnd_gray])

    return color_distort

def get_transform(train=True, crop=True, hflip=True, vflip=False, color_dis=True, blur=True, resize=None):
    transform = transforms.Compose([])

    if train:
        if crop:
            len_trans = len(transform.transforms)
            # transform.transforms.insert(len_trans, transforms.RandomResizedCrop(size=(IMG_SIZE, IMG_SIZE), \
                                                                        # interpolation=Image.BICUBIC))
            transform.transforms.insert(len_trans, transforms.CenterCrop(size=(IMG_SIZE, IMG_SIZE)))
        if hflip:
            len_trans = len(transform.transforms)
            transform.transforms.insert(len_trans, transforms.RandomHorizontalFlip())
        if color_dis:
            len_trans = len(transform.transforms)
            transform.transforms.insert(len_trans, get_color_distortion())
        if vflip:
            len_trans = len(transform.transforms)
            transform.transforms.insert(len_trans, transforms.RandomVerticalFlip())
        if resize is not None:
            len_trans = len(transform.transforms)
            transform.transforms.insert(len_trans, transforms.Resize((resize, resize), interpolation=Image.BICUBIC))
    else:
        if resize is not None:
            len_trans = len(transform.transforms)
            transform.transforms.insert(len_trans, transforms.Resize((IMG_SIZE, IMG_SIZE), interpolation=Image.BICUBIC))

    len_trans = len(transform.transforms)
    transform.transforms.insert(len_trans, transforms.ToTensor())

    del len_trans

    return transform

def calc_mean_std(dataloader):
    ''' Calculate mean and standard deviation of dataset '''
    pop_mean = []
    pop_std = []

    for data in dataloader:
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
    else:
        dataset = torchvision.datasets.ImageFolder(path, transform=transform)

    return dataset

def dataloader(data, path=None, train=False, transform=None, batch_size=1, iter=0, verbose=False, sampling=-1, \
               normalize=True, subset=None):
    
    # if data == 'imagenet':
    #     temp_trans = transforms.Compose([transforms.CenterCrop((500, 500)), transforms.ToTensor()])
    # elif data == 'mnist':
    #     temp_trans = transforms.Compose([transforms.CenterCrop((28, 28)), transforms.ToTensor()])
    # else:
    #     temp_trans = transforms.Compose([transforms.ToTensor()])
    # dataset = get_dataset(data, path, transform=temp_trans, train=train, iter=iter, verbose=verbose)
    dataset = get_dataset(data, path, transform, train=train, verbose=verbose, iter=iter)

    if subset is not None:
        subset_iter = list(np.random.choice(dataset.__len__(), size=subset, replace=False))
        dataset = CustomSubset(dataset, subset_iter)

    if train or not train:
        print(f'Using RandomSampler, train is {train}')
        sampler = RandomSampler(dataset)
    else:
        print(f'Using SequentialSampler, train is {train}')
        sampler = SequentialSampler(dataset)

    def seed_worker(worker_id):
        worker_seed = torch.initial_seed() % 2**32
        np.random.seed(worker_seed)
        random.seed(worker_seed)

    g = torch.Generator()
    g.manual_seed(SEED)

    data_loader = DataLoader(dataset, batch_size=batch_size, sampler=sampler, num_workers=1, worker_init_fn=seed_worker, generator=g, drop_last=True)

    if normalize and not isinstance(transform.transforms[-1], torchvision.transforms.transforms.Normalize):
        # mean, std = calc_mean_std(data_loader)
        mean, std = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]

        # dataset.__settransform__(transform)
        
        len_transform = len(dataset.__gettransform__().transforms)
        dataset.__gettransform__().transforms.insert(len_transform, transforms.Normalize(mean, std))

    return data_loader, dataset.__gettransform__()

def loader(data, batch_size, verbose, iter=0, sampling=-1, subset=None, transform=None):
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
        return dataloader('imagenet', path=train_data_path, train=True, transform=transforms_tr_imagenet, batch_size=batch_size, iter=iter, verbose=verbose, subset=subset) 
    elif data == 'imagenet_test':
        transforms_te_imagenet = get_transform(train=False, crop=False, hflip=False, vflip=False, blur=False) if transform is None else transform
        
        return dataloader('imagenet', test_data_path, transform=transforms_te_imagenet, batch_size=batch_size, iter=iter, verbose=verbose, subset=subset)
    elif data == 'mnist_train':
        transforms_tr_mnist = get_transform(train=True, crop=False, hflip=False, vflip=False, color_dis=False, blur=False, resize=28)

        return dataloader('mnist', train=True, transform=transforms_tr_mnist, batch_size=batch_size, iter=iter, verbose=verbose, normalize=True, subset=subset)
    elif data == 'mnist_test':
        transforms_te_mnist = get_transform(train=False, crop=False, hflip=False, vflip=False, color_dis=False, blur=False, resize=28) if transform is None else transform

        return dataloader('mnist', train=False, transform=transforms_te_mnist, batch_size=batch_size, iter=iter, verbose=verbose, normalize=True, subset=subset)
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

        lines = []
        lines.append(f'Subset number: {iter}\n')
        for i, key in enumerate(self.label_dict.keys()):
            img_paths = glob.glob(os.path.join(data_path, key, img_format))

            if i in range(9) and self.verbose:
                lines.append(f'Label mapping: {key} --> {i} {self.name_dict[key]}\n')
            elif self.verbose:
                lines.append(f'Label mapping: {key} --> {i} {self.name_dict[key]}\n')
                lines.append(f'Original subset labels: {subset}\n')

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

        if not os.path.exists(CODES_TO_NAMES_FILE):
                with open(CODES_TO_NAMES_FILE, 'w') as f:
                    f.writelines(lines)
        else:
            with open(CODES_TO_NAMES_FILE, 'r') as f:
                existing_lines = f.readlines()
            if lines[-1] not in existing_lines:
                with open(CODES_TO_NAMES_FILE, 'a') as f:
                    f.writelines(lines)

    def __len__(self):
        return len(self.data)
    
    def __getitem__(self, idx):
        img = self.data[idx][0]
        label = self.data[idx][1]

        img = self.transform(img) if self.transform else transforms.ToTensor()(img)
        label = torch.tensor(label, dtype=torch.long)

        return (img, label)

    def __settransform__(self, transform):
        self.transform = transform

    def __gettransform__(self):
        return self.transform    

class CustomMNIST(Dataset):
    def __init__(self, path='./data/mnist', train=True, transform=None):
        super(CustomMNIST, self).__init__()

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

class CustomSubset(Subset):
    def __init__(self, dataset, indices):
        super(CustomSubset, self).__init__(dataset, indices)

    def __settransform__(self, transform):
        if hasattr(self.dataset, '__settransform__'):
            self.dataset.__settransform__(transform)
        else:
            raise AttributeError("CustomSubset has no attribute '__settransform__'")

    def __gettransform__(self):
        return self.dataset.__gettransform__()
