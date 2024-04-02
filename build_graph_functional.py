from __future__ import print_function

import argparse
import time

from gph import ripser_parallel
# from gtda.homology import VietorisRipsPersistence, SparseRipsPersistence
from gtda.homology._utils import _postprocess_diagrams
from gtda.utils import check_diagrams
from scipy.sparse import coo_matrix

from bettis import betti_nums
from config import UPPER_DIM
from graph import *
from loaders import *
from models.utils import get_model
from passers import Passer
from utils import *

parser = argparse.ArgumentParser(description='Build Graph and Compute Betti Numbers')

parser.add_argument('--net')
parser.add_argument('--dataset')
parser.add_argument('--save_dir')
parser.add_argument('--chkpt_epochs', nargs='+', action='extend', type=int, default=[])
parser.add_argument('--subset', default=500, type=int, help='Subset size for building graph.')
parser.add_argument('--metric', default=None, type=str, help='Distance metric: "spearman", "dcor", or callable.')
parser.add_argument('--thresholds', default='0. 1.0', help='Defining thresholds range in the form \'start stop\' ')
parser.add_argument('--eps_thresh', default=1., type=float)
parser.add_argument('--reduction', default=None, type=str, help='Reductions: "pca" or "umap"')
parser.add_argument('--iter', default=0, type=int)
parser.add_argument('--verbose', default=0, type=int)

args = parser.parse_args()

device_list = []
if torch.cuda.device_count() > 1:
    device_list = [torch.device('cuda:{}'.format(i)) for i in range(torch.cuda.device_count())]
    print("Using", torch.cuda.device_count(), "GPUs")
    for i, device in enumerate(device_list):
        print(f"Device {i}: {device}")
else:
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    device_list.append(device)
    print(f'Using {device}')

''' Create save directories to store images '''
SAVE_DIR = args.save_dir
print(f'\n ==> Save directory: {SAVE_DIR} \n')

if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

IMG_DIR = os.path.join(SAVE_DIR, 'images')
if not os.path.exists(IMG_DIR):
    os.makedirs(IMG_DIR)

THREED_IMG_DIR = os.path.join(IMG_DIR, '3d_images')
if not os.path.exists(THREED_IMG_DIR):
    os.makedirs(THREED_IMG_DIR)

PERS_DIR = os.path.join(IMG_DIR, 'persistence')
if not os.path.exists(PERS_DIR):
    os.makedirs(PERS_DIR)

CURVES_DIR = os.path.join(IMG_DIR, 'curves')
if not os.path.exists(CURVES_DIR):
    os.makedirs(CURVES_DIR)

# Build models
print('\n ==> Building model..')
net = get_model(args.net, args.dataset)
net = net.to(device_list[0])

''' Prepare criterion '''
criterion = nn.CrossEntropyLoss()

''' Prepare val data loader '''
functloader = loader(args.dataset+'_test', batch_size=100, iter=args.iter, subset=args.subset, verbose=False) # subset size

# start = float(args.thresholds.split(' ')[0])
# stop = float(args.thresholds.split(' ')[1])
# thresholds = np.linspace(start=start, stop=stop, num=75, dtype=np.float64) # for 2D plot

# eps_thresh = np.linspace(start=0., stop=args.eps_thresh, num=75) # for 3D plot

total_time = 0.

''' Load checkpoint and get activations '''
assert os.path.isdir('./checkpoint'), 'Error: no checkpoint directory found!'
with torch.no_grad():
    # rips = VietorisRipsPersistence(metric='precomputed', homology_dimensions=list(range(UPPER_DIM+1)), collapse_edges=True, n_jobs=-1)
    # sparse_rips = SparseRipsPersistence(metric='precomputed', homology_dimensions=list(range(UPPER_DIM+1)), epsilon=0.1,  reduced_homology=True, n_jobs=-1)
    for epoch in vars(args)['chkpt_epochs']:
        print(f'\n==> Loading checkpoint for epoch {epoch}...\n')
        
        if args.dataset == 'imagenet':
            checkpoint = torch.load(f'./checkpoint/{args.net}/{args.net}_{args.dataset}_ss{args.iter}/ckpt_epoch_{epoch}.pt', map_location=device_list[0])
        else:
            checkpoint = torch.load(f'./checkpoint/{args.net}/{args.net}_{args.dataset}/ckpt_epoch_{epoch}.pt', map_location=device_list[0])
        
        net.load_state_dict(checkpoint['net'])
        net.eval()
        net.requires_grad_(False)

        ''' Define passer and get activations '''
        # get activations and reduce dimensionality; compute distance adjacency matrix
        passer = Passer(net, functloader, criterion, device_list[0])
        activs, orig_nodes = passer.get_function(reduction=args.reduction, device_list=device_list) 
        adj = adjacency(activs, metric=args.metric, device=device_list[0]) 

        num_nodes = adj.shape[0] if adj.shape[0] != 0 else 1

        if args.verbose:
            print(f'\n The dimension of the corrcoef matrix is {adj.size()[0], adj.size()[-1]} \n')
            print(f'Adj mean {adj.mean():.4f}, min {adj.min():.4f}, max {adj.max():.4f} \n')

        # betti_nums_list = []
        # betti_nums_list_3d = []
        # for j, t in enumerate(thresholds):
        # print(f'\n Epoch: {epoch}') # | Threshold: {t:.3f} \n')
        
        # binarize adjacency matrix
        # binadj = partial_binarize(adj.detach().clone(), t, device=device_list[-1]).detach()

        # convert to distance matrix via sqrt(1-adj) for V-R filtration; note that adj is absolute value of correlation
        adj *= -1
        adj += 1
        adj = torch.sqrt(adj)

        # convert to COO format for faster computation of persistence diagram
        indices = (adj<1.).nonzero().numpy(force=True)
        i = list(zip(*indices))
        vals = adj[i].flatten().numpy(force=True)

        adj = coo_matrix((vals, i), shape=adj.shape) if len(i) > 0 else coo_matrix(([], ([], [])), shape=adj.shape)

        del indices, i, vals

        if args.verbose:
            print(f'\n The dimension of the COO distance matrix is {adj.data.shape}\n')
            if adj.data.shape[0] != 0:
                print(f'adj mean {np.nanmean(adj.data):.4f}, min {np.nanmin(adj.data):.4f}, max {np.nanmax(adj.data):.4f}')
            else:
                print(f'adj empty! \n')
        
        # Compute persistence diagram
        comp_time = time.time()
        dgm = ripser_parallel(adj, metric="precomputed", maxdim=UPPER_DIM, n_threads=-1, collapse_edges=True)
        # dgm = rips.fit_transform([adj])
        comp_time = time.time() - comp_time
        total_time += comp_time
        print(f'\n Computation time: {comp_time/60:.5f} minutes \n')

        # free GPU memory
        del activs, adj, comp_time
        torch.cuda.empty_cache()

        check_time = time.time()
        dgm_gtda = _postprocess_diagrams([dgm["dgms"]], format="ripser", homology_dimensions=range(UPPER_DIM + 1), infinity_values=np.inf, reduced=True)[0]
        check_time = time.time() - check_time
        print(f'\n Check time: {check_time/60:.5f} minutes \n')

        if args.dataset == 'imagenet':
            dgm_pkl_file = f'./losses/{args.net}/{args.net}_{args.dataset}_ss{args.iter}/dgm_epoch_{epoch}.pkl'
        else:
            dgm_pkl_file = f'./losses/{args.net}/{args.net}_{args.dataset}/dgm_epoch_{epoch}.pkl'

        if not os.path.exists(os.path.dirname(dgm_pkl_file)):
            os.makedirs(os.path.dirname(dgm_pkl_file))

        with open(dgm_pkl_file, 'wb') as f:
            pickle.dump(dgm_gtda, f, protocol=pickle.HIGHEST_PROTOCOL)

        # # Compute betti numbers over eps. and thresh. for 3D plot
        # betti_nums_3d = []
        # for k in eps_thresh:
        #     betti_nums_3d.append(betti_nums(dgm_gtda, thresh=k))
        # betti_nums_list_3d.append(betti_nums_3d)
        
        # # Compute betti numbers at current eps. thresh.
        # betti_nums_list.append(betti_nums(dgm_gtda, thresh=args.eps_thresh))

        # # Plot persistence diagram at current eps. thresh.
        # if (t != 1.0) and (j % 25 == 0):
        #     dgm_img_path = PERS_DIR + "/epoch_{}_thresh{:.2f}_b{}".format(epoch, t, UPPER_DIM) + ".png"

        #     dgm_fig = plot_diagram(dgm_gtda)
        #     dgm_fig.write_image(dgm_img_path)

        # betti_nums_list = np.array(betti_nums_list)
        # betti_nums_list_3d = np.array(betti_nums_list_3d)
        
        # # Plot betti numbers per dimension at current eps. thresh.
        # make_plots(betti_nums_list, betti_nums_list_3d, epoch, num_nodes, orig_nodes, thresholds, eps_thresh, CURVES_DIR, THREED_IMG_DIR, start, stop, args.net, args.dataset, args.iter)

        del num_nodes, orig_nodes, dgm, dgm_gtda

    print(f'\n Total computation time: {total_time/60:.5f} minutes \n')

    pkl_file = f'./losses/{args.net}/{args.net}_{args.dataset}/times.pkl'
    if not os.path.exists(os.path.dirname(pkl_file)):
        os.makedirs(os.path.dirname(pkl_file))
    with open(pkl_file, 'ab') as f:
        pickle.dump(total_time, f, protocol=pickle.HIGHEST_PROTOCOL)

    del passer, net, criterion, functloader, total_time, checkpoint
