import numpy as np

# Where to save topology results
SAVE_PATH = 'results'

# DIPHA
DIPHA_MAGIC_NUMBER = 8067171840
ID = 7

# Sets upper limit for epsilon range in sparse distance matrix computation
MAX_EPSILON = 0.3

# Number of cores MPI can use
NPROC = 8

# Sets upper limit to dimension to compute for persistent homology.
UPPER_DIM = 3

# Size in pixels of square images
IMG_SIZE = 64

# Create 30 random lists of 10 class labels each for subsetting imagenet data
np.random.seed(1234)

lst = np.arange(1, 1000 + 1)
SUBSETS_LIST = [np.random.choice(lst, 10, replace=False) for _ in range(30)]
