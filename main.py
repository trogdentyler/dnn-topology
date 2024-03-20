import argparse
import os


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument('--train', default=1, type=int)
    parser.add_argument('--build_graph', default=1, type=int)
    parser.add_argument('--net', help='Specify deep network architecture.')
    parser.add_argument('--dataset', help='Specify dataset (e.g. mnist, cifar10, imagenet)')
    parser.add_argument('--subset', default=500, type=int, help='Subset size for building graph.')
    parser.add_argument('--metric', default=None, type=str, help='Distance metric: "spearman", "dcor", or callable.')
    parser.add_argument('--n_epochs_train', default='50', help='Number of epochs to train.')
    parser.add_argument('--lr', default='0.001', help='Specify learning rate for training.')
    parser.add_argument('--optimizer', default='adabelief', help='Define optimizer for training: "adabelief" or "adam"')
    parser.add_argument('--epochs_test', default='0 4 8 20 30 40 50', help='Epochs for which you want to build graph.')
    parser.add_argument('--thresholds', default='0.05 1.0', help='Define thresholds range in the form \'start stop\' ')
    parser.add_argument('--reduction', default=None, type=str, help='Reductions: "pca" or "umap"')
    parser.add_argument('--iter', type=int, default=0)
    parser.add_argument('--verbose', default=0, type=int)
    parser.add_argument('--save_dir', default='./results/', help='Directory to save results.')

    args = parser.parse_args()

    def visible_print(message):
        ''' Visible print'''
        print('')
        print(50*'-')
        print(message)
        print(50*'-')
        print('')

    if args.dataset.__eq__('mnist'):
        ONAME = f'{args.net}_{args.dataset}'
    else:
        ONAME = f'{args.net}_{args.dataset}_ss{args.iter}'
    SAVE_DIR = os.path.join(args.save_dir, ONAME)

    if args.train:
        visible_print('Training network')

        cmd = f'python ./train.py --save_dir {SAVE_DIR} --net {args.net} --dataset {args.dataset} --epochs {args.n_epochs_train} --lr {args.lr} --iter {args.iter} --chkpt_epochs {args.epochs_test} --optimizer {args.optimizer}'

        os.system(cmd)

    if args.build_graph:
        visible_print('Building graph')
        
        cmd = f'python ./build_graph_functional.py --save_dir {SAVE_DIR} --net {args.net} --dataset {args.dataset} --chkpt_epochs {args.epochs_test} --iter {args.iter} --verbose {args.verbose} --subset {args.subset}'
        cmd += f' --reduction {args.reduction}' if args.reduction else ''
        cmd += f' --metric {args.metric}' if args.metric else ''

        os.system(cmd)
