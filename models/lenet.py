import torch
import torch.nn as nn
import torch.nn.functional as F

    
class LeNet(nn.Module):
    def __init__(self, num_classes, num_channels=1, input_size=32):
        super(LeNet, self).__init__()

        self.feat_size = (20 * 5 * 5) if input_size==32 else (20 * 13 * 13) if input_size==64 else (20 * 4 * 4) if input_size==28 else -1
        
        self.conv1 = nn.Conv2d(num_channels, 10, kernel_size=5)
        self.conv2 = nn.Conv2d(10, 20, kernel_size=5)
        self.conv2_drop = nn.Dropout2d()
        self.fc1 = nn.Linear(self.feat_size, 50)
        self.fc2 = nn.Linear(50, num_classes)

    def forward(self, x):
        # print("x size: ", x.size())
        x1 = F.relu(F.max_pool2d(self.conv1(x), 2))
        x2 = F.relu(F.max_pool2d(self.conv2_drop(self.conv2(x1)), 2))
        # print("F Size x2: ", x2.size())
        x2 = x2.view(x2.size(0), -1)
        x3 = F.relu(self.fc1(x2))
        x4 = F.log_softmax(self.fc2(x3), dim=1)
        
        return x4
    
    def forward_features(self, x):
        x1 = F.relu(F.max_pool2d(self.conv1(x), 2))
        x2 = F.relu(F.max_pool2d(self.conv2_drop(self.conv2(x1)), 2))
        x2 = x2.view(-1, self.feat_size)
        x3 = F.relu(self.fc1(x2))
        x4 = F.log_softmax(self.fc2(x3), dim=1)

        return [x1, x2, x3, x4]

    def forward_param_features(self, x):
        return self.forward_features(x)

    
class LeNetExt(nn.Module):
    def __init__(self, n_channels, num_classes, input_size=32):
        super(LeNetExt, self).__init__()

        self.feat_size = (20 * 5 * 5) if input_size==32 else (20 * 13 * 13) if input_size==64 else -1

        self.conv1 = nn.Conv2d(n_channels, 10, kernel_size=5)
        self.conv2 = nn.Conv2d(10, 20, kernel_size=5)
        self.conv2_drop = nn.Dropout2d()
        self.fc1 = nn.Linear(self.feat_size, 120)
        self.fc2 = nn.Linear(120, 120)
        self.fc3 = nn.Linear(120,84)
        self.fc4 = nn.Linear(84, num_classes)

    def forward(self, x):
        out = F.relu(F.max_pool2d(self.conv1(x), 2))
        out = F.relu(F.max_pool2d(self.conv2_drop(self.conv2(out)), 2))
        # print("F Size out: ", out.size())
        out = out.view(out.size(0), -1)
        out = F.relu(self.fc1(out))
        out = F.relu(self.fc2(out))
        out = F.relu(self.fc3(out))
        # out = F.dropout(out, training=self.training)
        out = F.log_softmax(self.fc4(out), dim=1)

        return out
    
    def forward_features(self, x):
        x1 = F.relu(F.max_pool2d(self.conv1(x), 2))
        x2 = F.relu(F.max_pool2d(self.conv2_drop(self.conv2(x1)), 2))
        # print("FF Size x2: ", x2.size())
        x2 = x2.view(x2.size(0), -1)
        x3 = F.relu(self.fc1(x2))
        x4 = F.relu(self.fc2(x3))
        x5 = F.relu(self.fc3(x4))
        x6 = F.log_softmax(self.fc4(x5), dim=1)

        return [x1, x2, x3, x4, x5, x6]
